import csv
import yfinance as yf
from datetime import datetime, timedelta
import random
import time
import math
import requests
import json
import pandas as pd
import os

YFIN_KEYID = os.environ.get("YFIN_KEYID")
YFIN_KEY = os.environ.get("YFIN_KEY")

BASE_PATH = os.environ.get("BASE_PATH")

HEADERS = {"APCA-API-KEY-ID": YFIN_KEYID, "APCA-API-SECRET-KEY": YFIN_KEY}

'''
(in prog) update, check for two up days instead of just one, after hammer pattern

'''

myLookupFile = BASE_PATH + 'yfin/tickers.csv'

ticker_list = []


with open(myLookupFile, 'r') as x:

    reader = list(csv.reader(x))

    for line in reader[1:]:
        # print(line)
        ticker_list.append(line[0])


def check_trend(df):

    try:

        df['SMA15'] = df['c'].rolling(15).mean()
        count = 0
        for i in range(12):
            if df['SMA15'].iloc[-1 - (15 * i)] > df['SMA15'].iloc[-16 - (15 * i)]:
                count += 1
                print(count)
        print(f'count 15 SMA up: {count}\n\n')
        if count >= 10:
            return True

    except Exception as e:
        print(f'fail check_trend(): {e}')


def hammer(df, offset):

    try:

        day_offset = offset
        # new argument day, allows multiple days search (in dev still, not efficient to get df each day...)
        df['SMA50'] = df['c'].rolling(50).mean()
        df['SMA200'] = df['c'].rolling(200).mean()
        df['SMA20_VOL'] = df['v'].rolling(20).mean()

        low = df['l'].iloc[day_offset - 2]  # need -2 for hammer detection
        high = df['h'].iloc[day_offset - 2]
        open = df['o'].iloc[day_offset - 2]
        close = df['c'].iloc[day_offset - 2]

        body_perc = abs(close - open) / (high - low)
        top_bias = (high - close) / (high - low)

        # check for basic hammer features (body less than 25% of overall price range, body near top of range)
        if body_perc < .25 and top_bias < .15:

            # check if volume above 250K, price in standard range
            if df['SMA20_VOL'].iloc[day_offset] > 400000 and 3 < close < 100:

                # check if following day was up
                if df['c'].iloc[day_offset] > df['c'].iloc[day_offset - 1] > df['c'].iloc[day_offset - 2]:

                    # check for n days down prior to hammer
                    if down_days(df, day_offset):

                        return True

    except Exception as e:
        print(f'fail hammer(): {e}')


def down_days(df, offset):

    try:
        # check for drops in a range of previous days
        day_offset = offset
        count = 0
        days_down = 4
        days_down_range = 6
        # check if day before most recent is lower than the beginning of the range (confirm short term trend is downward)
        # trick here is to remember that we're looking for an up day, on most recent
        for i in range(days_down_range):
            # CONFIRM THESE OFFSETS, MAY NOT BE CORRECT for hammer plus 2 up days
            if df['c'].iloc[day_offset - 3 - i] < df['c'].iloc[day_offset - 4 - i]:
                count += 1

        if count >= days_down:
            return True

    except Exception as e:
        print(f'fail down_days(): {e}')


def find_pattern():

    try:

        symbol = random.choice(ticker_list)  # get random stock
        print(symbol)

        now = datetime.now()  # get random date
        day_range = 1450  # num days to look back for random date
        rand = random.randrange(0, day_range)
        then = now - timedelta(days=rand)  # random date in past
        then2 = then - timedelta(days=360)  # one year earlier
        end = then.strftime("%Y-%m-%d")
        start = then2.strftime("%Y-%m-%d")

        base_url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars?start={start}&end={end}&timeframe=1Day"
        r = requests.get(base_url, headers=HEADERS)
        x = json.loads(r.content)  # creates a dict
        dicts = x['bars']  # separates the list of dict called 'bars'
        df = pd.DataFrame(dicts)  # create df from that list of dict

        # check for general up trend
        if check_trend(df):

            # look back 90 days for hammer pattern
            for i in range(90):
                day_offset = -i
                # print(day_offset)
                if hammer(df, day_offset):

                    pdate = df['t'].iloc[day_offset]
                    pdate = pdate[:10]

                    pprice = df['c'].iloc[day_offset]
                    print(f'\n{symbol} p_date: {pdate} p_price: {pprice}\n\n')

                    p_date = datetime.strptime(pdate, "%Y-%m-%d")

                    earnings(symbol, p_date, pprice, calc_trail(df, day_offset))

                    break  # find next stock

    except Exception as e:
        print(f'fail find_pattern(): {e}')


def calc_trail(df, day_offset):

    try:

        df['tr0'] = abs(df['h'] - df['l'])
        df['tr1'] = abs(df['h'] - df['c'].shift())
        df['tr2'] = abs(df['l'] - df['c'].shift())
        df['trmax'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)

        df['atr_fact'] = df['trmax'].rolling(14).mean() * 2.0  # atr times some factor

        # print(df)
        return df['atr_fact'].iloc[day_offset] / df['c'].iloc[day_offset]  # return percentage of price

    except Exception as e:
        print(f'fail calc_trail(): {e}')


def earnings(symbol, p_date, p_price, tr_perc):

    try:

        with open('out.csv', 'a') as wf:

            writer = csv.writer(wf)

            total_earnings = 0

            spend = 1000
            shares = math.floor(spend / p_price)

            tr_percent = tr_perc

            if tr_percent < .05:  # set min and max values for tr perc
                tr_percent = .05
            if tr_percent > .15:
                tr_percent = .15

            print(f'trailing percent: {tr_percent}')

            # end_date = end_date.strftime("%Y-%m-%d")
            p_date_str = p_date.strftime("%Y-%m-%d")

            df_signal = pd.DataFrame({'highest': [.01]})  # prime a dummy df to later append to

            for i in range(120):

                try:

                    xx = p_date + timedelta(days=i)
                    yy = xx + timedelta(days=1)  # just get one day of min bars at a time
                    start = xx.strftime("%Y-%m-%d")
                    end = yy.strftime("%Y-%m-%d")

                    print(start, end)

                    base_url2 = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars?start={start}&end={end}&timeframe=1Min"
                    r2 = requests.get(base_url2, headers=HEADERS)
                    x2 = json.loads(r2.content)  # creates a dict
                    dicts2 = x2['bars']  # separates the list of dict called 'bars'
                    df2 = pd.DataFrame(dicts2)  # create df from that list of dict

                    df2['t'] = df2['t'].astype('datetime64[ns]')  # change object type to datetime
                    df2 = df2.set_index(df2['t'])  # reset index using datetime
                    df3 = df2.between_time('13:30:00', '20:00:00')  # use between_time method on index, create a new df with only these times

                    df_signal = df_signal.append(df3, ignore_index=True)  # append new df3 instead of df2
                    df_signal['highest'] = df_signal['h'].cummax()
                    df_signal['trailingstop'] = df_signal['highest'] * (1 - tr_percent)
                    df_signal['exit_signal'] = df_signal['l'] < df_signal['trailingstop']

                    # print(df_signal)
                    # print(df2)
                    time.sleep(.5)

                    if df_signal['exit_signal'].isin([True]).any():  # if True present (stop)...
                        id_sell = df_signal.exit_signal.ne(False).idxmax()  # get index of first True
                        print(f'id_sell is {id_sell}')
                        sell_price = df_signal['c'].iloc[id_sell]  # get price at trigger
                        earnings = (0.985 * sell_price * shares) - (p_price * shares)  # subtract bit (1.5%?) for falling price market sale
                        print(f'sell trigger for {symbol} is: {df_signal["t"].iloc[id_sell]}\nsell trigger price for {symbol} is: {sell_price}')
                        print(f'earnings for {symbol}: {earnings}')

                        days_held = df_signal["t"].iloc[id_sell] - p_date

                        row = [symbol, shares, p_date_str, df_signal["t"].iloc[id_sell], days_held, p_price, sell_price, tr_percent, earnings]
                        writer.writerow(row)

                        break

                    else:
                        print(f"haven't seen stop yet at day {i}")

                except Exception as e:
                    print(f'failed loop, error: {e}')

    except Exception as e:
        print(f'FAIL earnings(): {e}')


def main():

    count = 30000

    for i in range(count):

        print(f'count {i} of {count}')

        try:
            find_pattern()
        except Exception as e:
            print(f'FAIL main: {e}')

        time.sleep(.33)


if __name__ == "__main__":
    main()
