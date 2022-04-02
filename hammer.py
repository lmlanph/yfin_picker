import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import devmail_yfin as dm
import csv
import time
import math
import requests
import json
import os

'''
new: using 1 min bar alpaca, earnings

check for n number of down days in a given range, general up trend
then check for hammer pattern, followed by one day higher close

'''

YFIN_KEYID = os.environ.get("YFIN_KEYID")
YFIN_KEY = os.environ.get("YFIN_KEY")

BASE_PATH = os.environ.get("BASE_PATH")

HEADERS = {"APCA-API-KEY-ID": YFIN_KEYID, "APCA-API-SECRET-KEY": YFIN_KEY}

myLookupFile = BASE_PATH + 'yfin/tickers.csv'

ticker_list = []
day_offset = -1  # use -1 for current day (or yesterday, if before mkt open)

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

        low = df['l'].iloc[day_offset - 1]  # need -2 for hammer detection
        high = df['h'].iloc[day_offset - 1]
        open = df['o'].iloc[day_offset - 1]
        close = df['c'].iloc[day_offset - 1]

        body_perc = abs(close - open) / (high - low)
        top_bias = (high - close) / (high - low)

        # check for basic hammer features (body less than 25% of overall price range, body near top of range)
        if body_perc < .25 and top_bias < .15:

            # check if volume above 250K, price in standard range
            if df['SMA20_VOL'].iloc[day_offset] > 400000 and 3 < close < 100:

                        # # # check if hammer touching 50 SMA (-2 to match hammer pattern)
                        # if low < df['SMA50'].iloc[day_offset - 1] < high:

                #     #     # check if following day was up
                if df['c'].iloc[day_offset] > df['c'].iloc[day_offset - 1]:

                    #         # check for n days down prior to hammer
                    if down_days(df, day_offset):

                        #             # check if hammer pattern tall enough
                        #             if abs(high - low) > calc_trail(df, day_offset) * 1.1 * close:

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
            if df['c'].iloc[day_offset - 2 - i] < df['c'].iloc[day_offset - 3 - i]:
                count += 1

        if count >= days_down:
            return True

    except Exception as e:
        print(f'fail down_days(): {e}')


def find_pattern(ticker):

    try:

        symbol = ticker

        now = datetime.now() - timedelta(days=1)
        then = now - timedelta(days=360)  # enough days to look back for trend
        end = now.strftime("%Y-%m-%d")
        start = then.strftime("%Y-%m-%d")
        print(f'start and end: {start} {end}')

        base_url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars?start={start}&end={end}&timeframe=1Day"
        r = requests.get(base_url, headers=HEADERS)
        x = json.loads(r.content)  # creates a dict
        dicts = x['bars']  # separates the list of dict called 'bars'
        df = pd.DataFrame(dicts)  # create df from that list of dict
        # print(df)

        # check for general up trend
        if check_trend(df):

            if hammer(df, day_offset):

                pdate = df['t'].iloc[day_offset]  # check for off-by-one-day error
                pdate = pdate[:10]

                pprice = df['c'].iloc[day_offset]  # check for off-by-one-day error
                print(f'\n{symbol} p_date: {pdate} p_price: {pprice}\n\n')

                pdate = datetime.strptime(pdate, "%Y-%m-%d")

                return True

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


def main():

    list = []
    count = 0
    for ticker in ticker_list:
        count += 1
        print(count, ticker)

        try:

            if find_pattern(ticker):
                list.append(ticker)

            print(f'your list: {list}')

            time.sleep(.33)

        except Exception as e:
            print(e)

    l = '", "'.join(list)
    dm.mailMe(f'[bt9 copy via alpaca] list contains: "{l}"')


if __name__ == "__main__":
    main()
