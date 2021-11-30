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

# POTENTIAL ERRORS: Rounding (price to 2, other values to 5)

BALANCE_FILENAME = "CRYPTO_BALANCE_HISTORY.csv"
log_df = None
try:
    log_df = get_csv_log(BALANCE_FILENAME)
except:
    print("No log file of name '" + BALANCE_FILENAME + "' was found. Exiting.")
    sys.exit()

binance_client = Client(
    "Oe9hWnotHo6Z185qVjQpnZuGi91sUGXEBqbaTDqUXDQq4ejEyfaFEpjBt5jRKKPI",
    "tUQK6WSXwj8lrGZjPq7AyKQ0DYBA6uhWRXMg0J1xm99XFMRtqdSHIF3XycduYCf1"
)

# Multiplier/divisor for order prices
SYMBOL = "BNB"
Q_ROUND = 3
P_ROUND = 2

BUY_RATIO = 0.9935
SELL_RATIO = 1.0025
RSI_PERIOD = 10
BUY_RSI = 20
SELL_RSI = 50

status = binance_client.get_system_status()
print(status)

symbol_info = binance_client.get_symbol_info(SYMBOL + 'USDT')
#print(symbol_info)
print("\n--------------\n")

P_ROUND = math.ceil(-math.log(float(symbol_info['filters'][0]['tickSize']), 10))
Q_ROUND = math.ceil(-math.log(float(symbol_info['filters'][2]['stepSize']), 10))

#us_balance = float(client.get_asset_balance("USDT")["free"])

crypto_balance = float(binance_client.get_asset_balance(SYMBOL)["free"])

bought = False
if crypto_balance >= 0.01:
    bought = True
start_cash = float(binance_client.get_asset_balance(asset='USDT')['free'])
buy_price = sys.float_info.max
attempt_buy = sys.float_info.max
attempt_sell = 0
def make_trade():
    global bought
    global start_cash
    global buy_price
    global attempt_buy
    global attempt_sell
    global binance_client
    # Get historical K-line data
    hist_values = np.matrix(binance_client.get_historical_klines(SYMBOL + "USDT", Client.KLINE_INTERVAL_1MINUTE, "2 hours ago UTC"))
    current_time = int(round(time.time(), -1)*1000)
    data_time = int(hist_values[len(hist_values)-1, 0])
    # Make sure data is up to date
    while current_time != data_time:
        hist_values = np.matrix(binance_client.get_historical_klines(SYMBOL + "USDT", Client.KLINE_INTERVAL_1MINUTE, "2 hours ago UTC"))
        current_time = int(round(time.time(), -1) * 1000)
        data_time = int(hist_values[len(hist_values) - 1, 0])
    # Get last 6 data points
    hist_values = hist_values[:,4].T.tolist()[0]
    hist_values = [float(value) for value in hist_values]
    # Get rid of most recent value (the one that is continuously changing) and irrelevant earlier values
    start_index = len(hist_values) - 1 - 96
    prev = hist_values[start_index:len(hist_values)-1]
    #Get price
    price = hist_values[len(hist_values)-1]
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

    info_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "|$P: " + str(round(last_price, 2)) + "|$P/96m_MA: " + str(round(price/MA_96, 4)) + "|RSI: " + str(round(rsi, 2))
    if bought:
        info_str += "|$P/BUY_$P: " + str(round(last_price/buy_price, 4)) + "|->SELL "


    print(info_str)

    # ALWAYS round to 5 decimals
    if price/MA_96 <= BUY_RATIO and rsi <= BUY_RSI and not bought:
        # Get balance
        usdt_balance = float(binance_client.get_asset_balance(asset='USDT')['free'])
        start_cash = usdt_balance
        BUY_AMOUNT = usdt_balance * 0.995

        if BUY_AMOUNT < 11:
            print(str_ylw("Attempted to buy, balance not high enough."))
            return

        # --- PLACE BUY ORDER ---
        quantity = round(BUY_AMOUNT / price, Q_ROUND)
        quantity_str = '{:0.0{}f}'.format(quantity, Q_ROUND)
        #print("Buying " + str(BUY_AMOUNT) + "USDT / " + quantity_str + SYMBOL + "...")
        order = binance_client.order_market_buy(
            symbol=SYMBOL + 'USDT',
            quantity=quantity_str
        )
        bought = True
        attempt_buy = sys.float_info.max
        try:
            buy_price = round(float(order['fills'][0]['price']), 2)
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
    elif ((last_price/buy_price >= SELL_RATIO and rsi >= SELL_RSI) or price/buy_price >= (SELL_RATIO + 0.0005) or rsi >= 90) and bought:
        balance = float(binance_client.get_asset_balance(asset=SYMBOL)['free'])
        #balance -= math.pow(0.1, Q_ROUND)*0.5
        # Keep 0.5% of BNB to save on fees
        quantity = round(balance*0.995, Q_ROUND)

        # --- PLACE SELL ORDER ---

        #Format quantity string
        quantity_str = '{:0.0{}f}'.format(quantity, Q_ROUND)
        order = binance_client.order_market_sell(
            symbol=SYMBOL + 'USDT',
            quantity=quantity_str
        )
        bought = False
        attempt_sell = 0
        try:
            sell_price = order['fills'][0]['price']
        except:
            sell_price = "n/a"
        # Get balance
        usdt_balance = float(binance_client.get_asset_balance(asset='USDT')['free'])
        profit = round((usdt_balance - start_cash)/start_cash*100, 3)
        start_cash = usdt_balance
        sell_str = "Sold " + str(quantity) + SYMBOL + " at price of " + str(sell_price) + " (BALANCE: " + str(
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