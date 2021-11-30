from binance.client import Client
from binance.enums import *
import sched, time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import numpy as np
from ColorPrint import *
import math
from SendEmail import send_mail, send_sms
import sys

# POTENTIAL ERRORS: Rounding (price to 2, other values to 5)

binance_client = Client()

# Multiplier/divisor for order prices
SYMBOL = "BNB"
Q_ROUND = 3
P_ROUND = 2

BUY_RATIO = -0.02
SELL_RATIO = 0.015
TRAIL_LIMIT = 0.0015
STOP_LOSS = 0.96

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
    #MA_96 = np.mean(prev)
    #MA_6 = np.mean(prev[len(prev) - 6:])
    #MA_12 = np.mean(prev[len(prev) - 12:])
    MA_24 = np.mean(prev[len(prev) - 24:])
    #LAST_MA_12 = np.mean(prev[len(prev) - 13:len(prev)-1])
    LAST_MA_24 = np.mean(prev[len(prev) - 25:len(prev) - 1])
    CHNG_24 = (MA_24 - LAST_MA_24)/LAST_MA_24*100
    # --- PRINT INFO ---

    info_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "|$P: " + str(round(last_price, 2)) + "|24m_MA %CHNG: " + str(round(CHNG_24, 4))
    if bought:
        info_str += "|$P/BUY_$P: " + str(round(last_price/buy_price, 4)) + "|->SELL "
        if CHNG_24 >= SELL_RATIO or attempt_sell > 0:
            info_str = str_ylw(info_str)
    else:
        info_str += "|->BUY"
        if (CHNG_24 <= BUY_RATIO or attempt_buy < 999999):
            info_str = str_ylw(info_str)

    print(info_str)

    # ALWAYS round to 5 decimals
    if (CHNG_24 <= BUY_RATIO or attempt_buy < 999999) and not bought:
        # Get balance
        usdt_balance = float(binance_client.get_asset_balance(asset='USDT')['free'])
        crypto_balance = float(binance_client.get_asset_balance(asset=SYMBOL)['free'])
        start_cash = usdt_balance + crypto_balance*price
        BUY_AMOUNT = usdt_balance * 0.995

        if BUY_AMOUNT < 11:
            print(str_ylw("Attempted to buy, balance not high enough."))
            return

        if last_price < attempt_buy:
            attempt_buy = last_price

        current_price = float(np.matrix(binance_client.get_historical_klines(SYMBOL + "USDT", Client.KLINE_INTERVAL_1MINUTE, "1 minute ago UTC"))[0, 4])

        while current_price <= attempt_buy*(1 + TRAIL_LIMIT):
            time.sleep(0.2)
            now = int(datetime.now().strftime("%S"))
            if now == 58:
                return
            # Get current price
            try:
                current_price = float(np.matrix(binance_client.get_historical_klines(SYMBOL + "USDT", Client.KLINE_INTERVAL_1MINUTE, "1 minute ago UTC"))[0, 4])
            except:
                continue

        # --- PLACE BUY ORDER ---
        quantity = round(BUY_AMOUNT / current_price, Q_ROUND)
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
    elif (CHNG_24 >= SELL_RATIO or attempt_sell > 0) and bought:
        balance = float(binance_client.get_asset_balance(asset=SYMBOL)['free'])
        balance -= math.pow(0.1, Q_ROUND)*0.5
        quantity = round(balance, Q_ROUND)

        if last_price > attempt_sell:
            attempt_sell = last_price

        current_price = float(
            np.matrix(binance_client.get_historical_klines(SYMBOL + "USDT", Client.KLINE_INTERVAL_1MINUTE, "1 minute ago UTC"))[
                0, 4])

        while current_price >= attempt_sell * (1 - TRAIL_LIMIT):
            time.sleep(0.2)
            now = int(datetime.now().strftime("%S"))
            if now == 58:
                return
            # Get current price
            try:
                current_price = float(np.matrix(binance_client.get_historical_klines(SYMBOL + "USDT", Client.KLINE_INTERVAL_1MINUTE, "1 minute ago UTC"))[0, 4])
            except:
                continue

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
        #print(order)

#make_trade()
print("Bot started!")
schedule = BlockingScheduler()
#schedule.add_job(make_trade, 'interval', minutes=5)
schedule.add_job(make_trade, 'cron', second="59")
schedule.start()