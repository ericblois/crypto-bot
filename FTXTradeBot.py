from binance.client import Client
from binance.enums import *
import sched, time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import numpy as np
from ColorPrint import *
import math
from SendEmail import *
import sys
import ftx

# POTENTIAL ERRORS: Rounding (price to 2, other values to 5)

BALANCE_FILENAME = "CRYPTO_BALANCE_HISTORY.csv"
log_df = None
try:
    log_df = get_csv_log(BALANCE_FILENAME)
except:
    print("No log file of name '" + BALANCE_FILENAME + "' was found. Exiting.")
    sys.exit()

API_STRINGS = open("FTX_API_Key", 'r').readlines()
for i, string in enumerate(API_STRINGS):
    API_STRINGS[i] = string.strip()

API_KEY = API_STRINGS[0]
API_SECRET = API_STRINGS[1]
ftx_client = ftx.FtxClient(api_key=API_KEY, api_secret=API_SECRET)

# Length of intervals in minutes
INTERVAL = 1
# Number of historical prices to request
NUM_HIST_DATA = 120
# Multiplier/divisor for order prices
SYMBOL = "BNB"
Q_ROUND = 2
P_ROUND = 3

BUY_RATIO = 0.9935
SELL_RATIO = 1.0025
RSI_PERIOD = 10
BUY_RSI = 20
SELL_RSI = 50

# --- Get balances ---

balances = ftx_client.get_balances()
crypto_balance = 0
start_cash = 0
for value in balances:
    if value['coin'] == SYMBOL:
        crypto_balance = float(value['free'])
    elif value['coin'] == "USDT":
        start_cash = float(value['free'])

# --- Set up function parameters ---

bought = False
if crypto_balance >= 0.01:
    bought = True
buy_price = sys.float_info.max
def make_trade():
    global bought
    global start_cash
    global buy_price
    global ftx_client
    global balances
    global crypto_balance
    # Get historical data
    now = time.time()
    data = ftx_client.get_historical_data(SYMBOL + "/USDT", INTERVAL * 60, limit=1440, start_time=now - (NUM_HIST_DATA * INTERVAL * 60 + INTERVAL * 60), end_time=now)
    # Make sure data is up to date
    while round(time.time() - 5, -1) * 1000 != data[len(data) - 1]['time']:
        now = time.time()
        data = ftx_client.get_historical_data(SYMBOL + "/USDT", INTERVAL * 60, limit=1440, start_time=now - (NUM_HIST_DATA * INTERVAL * 60 + INTERVAL * 60), end_time=now)
    # Convert received data to list of close prices
    hist_values = [value['close'] for value in data]
    # Get rid of most recent value (the one that is continuously changing) and irrelevant earlier values
    start_index = len(hist_values) - 1 - 96
    prev = hist_values[start_index:len(hist_values)-1]
    #Get price
    last_price = hist_values[len(hist_values) - 2]
    # Get past LONG_AVG changes
    MA_96 = np.mean(prev)
    # Get RSI
    last = prev[len(prev) - (RSI_PERIOD + 1):]
    changes = [(value - last[i])/last[i]*100 for i, value in enumerate(last[1:])]
    gains = []
    losses = []
    for change in changes:
        if change > 0:
            gains.append(change)
            losses.append(0)
        elif change < 0:
            losses.append(change)
            gains.append(0)
    avg_gain = np.mean(gains)
    avg_loss = -np.mean(losses)
    rsi = 100 - (100 / (1 + avg_gain / (avg_loss + 0.0000000001)))
    # --- PRINT INFO ---

    info_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "|$P: " + str(round(last_price, 2)) + "|$P/96m_MA: " + str(round(last_price/MA_96, 4)) + "|RSI: " + str(round(rsi, 2))
    if bought:
        info_str += "|$P/BUY_$P: " + str(round(last_price/buy_price, 4)) + "|->SELL "


    print(info_str)

    # ALWAYS round to 5 decimals
    if last_price/MA_96 <= BUY_RATIO and rsi <= BUY_RSI and not bought:
        # Get trade price
        orderbook = ftx_client.get_orderbook(SYMBOL + "/USD", 1)
        trade_price = (orderbook['bids'][0][0] + orderbook['asks'][0][0]) / 2
        # Get balance
        balances = ftx_client.get_balances()
        usdt_balance = 0
        for value in balances:
            if value['coin'] == "USDT":
                usdt_balance = float(value['free'])
        start_cash = usdt_balance
        BUY_AMOUNT = usdt_balance * 0.995
        quantity = round(BUY_AMOUNT / trade_price, Q_ROUND)
        quantity -= math.pow(0.1, Q_ROUND)
        if BUY_AMOUNT < 11:
            print(str_ylw("Attempted to buy, balance not high enough."))
            return

        # --- PLACE BUY ORDER ---

        print(trade_price)
        print(quantity)
        print(usdt_balance)
        order = ftx_client.place_order(
            market=SYMBOL + "/USDT",
            side="buy",
            price=trade_price,
            type="limit",
            size=quantity
        )
        order_time = time.time()

        orders = ftx_client.get_open_orders()
        while len(orders) > 0:
            time.sleep(0.1)
            orders = ftx_client.get_open_orders()
            if time.time() - order_time > 50:
                ftx_client.cancel_orders()

        bought = True
        try:
            buy_price = round(trade_price, 2)
            buy_str = "Bought " + str(quantity) + SYMBOL + " at price of " + str(buy_price) + " (BALANCE: " + str(usdt_balance - BUY_AMOUNT) + "USDT)"
            print(str_cyn(buy_str))
            send_sms(buy_str)
            #send_mail("TradeBot has bought " + SYMBOL, buy_str)
        except:
            buy_str = "Bought " + str(quantity) + SYMBOL
            print(str_cyn(buy_str))
            send_sms(buy_str)
            #send_mail("TradeBot has bought " + SYMBOL, buy_str)

        #print(order)
    elif ((last_price/buy_price >= SELL_RATIO and rsi >= SELL_RSI) or last_price/buy_price >= (SELL_RATIO + 0.0005) or rsi >= 90) and bought:
        # Get balance and quantity to sell
        balances = ftx_client.get_balances()
        crypto_balance = 0
        for value in balances:
            if value['coin'] == SYMBOL:
                crypto_balance = float(value['free'])

        crypto_balance -= math.pow(0.1, Q_ROUND)*0.5
        quantity = round(crypto_balance, Q_ROUND)
        # Get trade price
        orderbook = ftx_client.get_orderbook(SYMBOL + "/USD", 1)
        trade_price = (orderbook['bids'][0][0] + orderbook['asks'][0][0]) / 2

        # --- PLACE SELL ORDER ---

        order = ftx_client.place_order(
            market=SYMBOL + "/USDT",
            side="sell",
            price=trade_price,
            type="limit",
            size=quantity
        )
        order_time = time.time()

        orders = ftx_client.get_open_orders()
        while len(orders) > 0:
            time.sleep(0.1)
            orders = ftx_client.get_open_orders()
            if time.time() - order_time > 50:
                ftx_client.cancel_orders()

        bought = False
        # Get balance
        balances = ftx_client.get_balances()
        usdt_balance = 0
        for value in balances:
            if value['coin'] == "USDT":
                usdt_balance = float(value['free'])
        profit = round((usdt_balance - start_cash)/start_cash*100, 3)
        start_cash = usdt_balance
        sell_str = "Sold " + str(quantity) + SYMBOL + " at price of " + str(trade_price) + " (BALANCE: " + str(
            usdt_balance) + "USDT, " + str(profit) + "% change)"
        send_sms(sell_str)
        if profit > 0:
            print(str_grn(sell_str))
            #send_mail("TradeBot has sold " + SYMBOL, sell_str)
        elif profit < 0:
            print(str_red(sell_str))
            #send_mail("TradeBot has sold " + SYMBOL, sell_str)
        else:
            print(str_mag(sell_str))
            #send_mail("TradeBot has sold " + SYMBOL, sell_str)
        date = datetime.now().strftime("%Y-%m-%d")
        time_now = datetime.now().strftime("%H:%M")
        add_df_row([date, time_now, usdt_balance, profit], log_df)
        save_csv_log(BALANCE_FILENAME, log_df)
        #print(order)

#make_trade()
print("Bot started!")
schedule = BlockingScheduler()
#schedule.add_job(make_trade, 'interval', minutes=5)
schedule.add_job(make_trade, 'cron', second="59")
schedule.start()