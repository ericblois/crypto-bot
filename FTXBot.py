import sys, ftx, sched, time, math
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import numpy as np
from ColorPrint import *
from SendEmail import *

# --- CLIENT VARIABLE ---

API_STRINGS = open("FTX_API_Key", 'r').readlines()
for i, string in enumerate(API_STRINGS):
    API_STRINGS[i] = string.strip()

API_KEY = API_STRINGS[0]
API_SECRET = API_STRINGS[1]
ftx_client = ftx.FtxClient(api_key=API_KEY, api_secret=API_SECRET)

# --- CONSTANTS ---

# Length of intervals in minutes
INTERVAL = 1
# Number of historical prices to request
NUM_HIST_DATA = 60
# Multiplier/divisor for order prices
SYMBOL = "BNB"

now = time.time()
market = ftx_client.get_market(SYMBOL + "/USDT")

Q_ROUND = math.floor(math.log(market['sizeIncrement'], 0.1))
P_ROUND = math.floor(math.log(market['priceIncrement'], 0.1))

SELL_RATIO = 1.01
LONG_RSI_PERIOD = 30
SHORT_RSI_PERIOD = 10
LONG_BUY_RSI = 35
SHORT_BUY_RSI = 20
SELL_RSI = 60

BALANCE_FILENAME = "CRYPTO_BALANCE_HISTORY.csv"
log_df = None
try:
    log_df = get_csv_log(BALANCE_FILENAME)
except:
    print("No log file of name '" + BALANCE_FILENAME + "' was found. Exiting.")
    sys.exit()

# --- FUNCTION VALUES ---

# Get balances
balances = ftx_client.get_balances()
usdt_balance = 0
crypto_balance = 0
start_cash = 0
for value in balances:
    if value['coin'] == SYMBOL:
        crypto_balance = float(value['free'])
    elif value['coin'] == "USDT":
        start_cash = float(value['free'])
# Set up function parameters
bought = False
if crypto_balance >= 0.01:
    bought = True
buy_price = 999999
if bought:
    buy_price = float(ftx_client.get_order_history()[0]['price'])
    start_cash = float(log_df.loc[len(log_df.index) - 1][2])
sell_trigger = False

def make_trade():
    try:
        global bought
        global start_cash
        global buy_price
        global ftx_client
        global balances
        global usdt_balance
        global crypto_balance
        global sell_trigger

        # --- GET BALANCES ---
        # Get balances just before next price update, to save on time when trade is executed
        balances = ftx_client.get_balances()
        usdt_balance = 0
        crypto_balance = 0
        for value in balances:
            if value['coin'] == "USDT":
                usdt_balance = float(value['free'])
            if value['coin'] == SYMBOL:
                crypto_balance = float(value['free'])

        # --- GET HISTORICAL PRICE DATA ---

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
        prev = hist_values[:len(hist_values)-1]
        # Get last price
        last_price = hist_values[len(hist_values) - 2]
        prev_price = hist_values[len(hist_values) - 3]

        # --- GET RSI VALUES ---

        last = prev[len(prev) - (LONG_RSI_PERIOD + 1):]
        changes = [(value - last[i])/last[i]*100 for i, value in enumerate(last[1:])]
        gains = []
        losses = []
        for i, change in enumerate(changes):
            if change > 0:
                gains.append(change)
                losses.append(0)
            elif change < 0:
                losses.append(change)
                gains.append(0)
        avg_gain = np.mean(gains)
        avg_loss = -np.mean(losses)
        long_rsi = 100 - (100 / (1 + avg_gain / (avg_loss + 0.0000000001)))
        avg_gain = np.mean(gains[len(gains)-SHORT_RSI_PERIOD:])
        avg_loss = -np.mean(losses[len(losses)-SHORT_RSI_PERIOD:])
        short_rsi = 100 - (100 / (1 + avg_gain / (avg_loss + 0.0000000001)))

        # --- PRINT INFO ---

        info_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")\
                   + "|$P: " + str(round(last_price, 2))\
                   + "|30m-RSI: " + str(round(long_rsi, 2))\
                   + "|10m-RSI: " + str(round(short_rsi, 2))
        if bought:
            info_str += "|$P/BUY_$P: " + str(round(last_price/buy_price, 4)) + "|->SELL"
        else:
            info_str += "|->BUY"

        print(info_str)

        if bought and short_rsi >= 40 and last_price/buy_price >= 1.0025:
            sell_trigger = True

        # ALWAYS round to 5 decimals
        if round(long_rsi) <= LONG_BUY_RSI and round(short_rsi) <= SHORT_BUY_RSI and not bought:

            # --- PREPARE TRADE NUMBERS

            # Get trade price
            orderbook = ftx_client.get_orderbook(SYMBOL + "/USD", 1)
            trade_price = (orderbook['bids'][0][0] + orderbook['asks'][0][0]) / 2
            start_cash = usdt_balance
            quantity = usdt_balance / trade_price
            # Floor the quantity value
            quantity *= math.pow(10, Q_ROUND)
            quantity = math.floor(quantity)/math.pow(10, Q_ROUND)

            # --- PLACE BUY ORDER ---

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

            # --- OUTPUT BUY INFORMATION ---

            # Get order price
            buy_price = float(ftx_client.get_order_history()[0]['price'])
            bought = True
            buy_str = "Bought " + str(quantity) + SYMBOL + " at price of " + str(buy_price) + " (BALANCE: " + str(usdt_balance - quantity*buy_price) + "USDT)"
            print(str_cyn(buy_str))
            send_sms(buy_str)

        elif (sell_trigger and last_price < prev_price) or (bought and round(long_rsi) >= 60):

            # --- PREPARE TRADE NUMBERS ---

            crypto_balance *= math.pow(10, Q_ROUND)
            quantity = math.floor(crypto_balance)/math.pow(10, Q_ROUND)
            # Get trade price
            orderbook = ftx_client.get_orderbook(SYMBOL + "/USD", 1)
            trade_price = (orderbook['bids'][0][0] + orderbook['asks'][0][0]) / 2 - 0.1

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
                if time.time() - order_time > 45:
                    ftx_client.cancel_orders()
                    return

            # --- OUTPUT SELL INFORMATION ---

            # Get sell price
            sell_price = float(ftx_client.get_order_history()[0]['price'])
            bought = False
            sell_trigger = False
            # Get balance
            order_time = time.time()
            balances = ftx_client.get_balances()
            usdt_balance = 0
            for value in balances:
                if value['coin'] == "USDT":
                    usdt_balance = float(value['free'])

            while usdt_balance < start_cash*0.5:
                balances = ftx_client.get_balances()
                usdt_balance = 0
                for value in balances:
                    if value['coin'] == "USDT":
                        usdt_balance = float(value['free'])
                if time.time() - order_time > 10:
                    usdt_balance += crypto_balance*sell_price
                    print("COULD NOT GET FINAL SALE BALANCE")

            profit = round((usdt_balance - start_cash)/start_cash*100, 3)
            start_cash = usdt_balance
            sell_str = "Sold " + str(quantity) + SYMBOL + " at price of " + str(sell_price) + " (BALANCE: " + str(
                usdt_balance) + "USDT, " + str(profit) + "% change)"
            send_sms(sell_str)
            if profit > 0:
                print(str_grn(sell_str))
            elif profit < 0:
                print(str_red(sell_str))
            else:
                print(str_ylw(sell_str))

            # --- LOG TRADE INFORMATION ---

            date = datetime.now().strftime("%Y-%m-%d")
            time_now = datetime.now().strftime("%H:%M")
            add_df_row([date, time_now, usdt_balance, profit], log_df)
            save_csv_log(BALANCE_FILENAME, log_df)
        if int(datetime.now().strftime("%M")) % 5 == 0:
            ftx_client = ftx_client = ftx.FtxClient(api_key=API_KEY, api_secret=API_SECRET)
    except Exception as e:
        error_string = "There was an error:\n\n" + str(e)
        send_sms(error_string)
        print(e)


#make_trade()
print("Bot started!")
schedule = BlockingScheduler()
schedule.add_job(make_trade, 'cron', second="57")
schedule.start()
