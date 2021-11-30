from binance.client import Client
from binance.enums import *
import sched, time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import numpy as np
from ColorPrint import *
import math
from SendEmail import send_mail

# POTENTIAL ERRORS: Rounding (price to 2, other values to 5)

proxies = {
    'http': 'http://10.10.1.10:3128',
    'https': 'http://10.10.1.10:1080'
}

binance_client = Client()

# Multiplier/divisor for order prices
SYMBOL = "BNB"
LONG_AVG = 180
SHORT_AVG = 60
Q_ROUND = 3
P_ROUND = 2

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
start_cash = 1
def make_trade():
    time.sleep(0.5)
    global bought
    global start_cash
    #Past 60 5-minute intervals
    hist_values = np.matrix(binance_client.get_historical_klines(SYMBOL + "USDT", Client.KLINE_INTERVAL_5MINUTE, "1 day ago UTC"))
    # Get last 6 data points
    hist_values = hist_values[:,4].T.tolist()[0]
    hist_values = [float(value) for value in hist_values]
    # Get rid of most recent value (the one that is continuously changing) and irrelevant earlier values
    start_index = len(hist_values) - 2 - LONG_AVG
    prev = hist_values[start_index:len(hist_values)-1]
    #Get price
    price = hist_values[len(hist_values)-1]
    # Get past LONG_AVG changes
    changes = [change - prev[i] for i, change in enumerate(prev[1:])]
    long_avg_change = sum(changes)/LONG_AVG
    short_avg_change = sum(changes[len(changes)-SHORT_AVG:])/SHORT_AVG

    # --- PRINT INFO ---

    info_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "|$P: " + str(round(price, 2)) + "|" + str(LONG_AVG) + "I-CHNG: " + str(round(long_avg_change, 2)) + "|" + str(SHORT_AVG) + "I-CHNG: " + str(round(short_avg_change, 2)) + "|RATIO: " + str(short_avg_change/abs(long_avg_change))
    if bought:
        info_str += "|->SELL"
    else:
        info_str += "|->BUY"

    print(info_str)

    # ALWAYS round to 5 decimals
    if short_avg_change <= long_avg_change*3 and not bought:
        # Get balance
        usdt_balance = float(binance_client.get_asset_balance(asset='USDT')['free'])
        crypto_balance = float(binance_client.get_asset_balance(asset=SYMBOL)['free'])
        start_cash = usdt_balance + crypto_balance*price
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
        try:
            buy_price = round(float(order['fills'][0]['price']), 2)
            buy_str = "Bought " + str(quantity) + SYMBOL + " at price of " + str(buy_price) + " (BALANCE: " + str(usdt_balance - BUY_AMOUNT) + "USDT)"
            print(str_cyn(buy_str))
            #send_mail("TradeBot has bought " + SYMBOL, buy_str)
        except:
            buy_str = "Bought " + str(quantity) + SYMBOL
            print(str_cyn(buy_str))
            #send_mail("TradeBot has bought " + SYMBOL, buy_str)

        #print(order)
    elif short_avg_change >= long_avg_change*3 and bought:
        balance = float(binance_client.get_asset_balance(asset=SYMBOL)['free'])
        balance -= math.pow(0.1, Q_ROUND)*0.5
        quantity = round(balance, Q_ROUND)

        # --- PLACE SELL ORDER ---

        #Format quantity string
        quantity_str = '{:0.0{}f}'.format(quantity, Q_ROUND)
        order = binance_client.order_market_sell(
            symbol=SYMBOL + 'USDT',
            quantity=quantity_str
        )
        bought = False
        try:
            sell_price = order['fills'][0]['price']
        except:
            sell_price = "n/a"
        # Get balance
        usdt_balance = float(binance_client.get_asset_balance(asset='USDT')['free'])
        crypto_balance = float(binance_client.get_asset_balance(SYMBOL)["free"])
        value = usdt_balance + crypto_balance * price
        profit = round((value - start_cash)/start_cash*100, 3)
        start_cash = value
        sell_str = "Sold " + str(quantity) + SYMBOL + " at price of " + str(sell_price) + " (BALANCE: " + str(
            usdt_balance) + "USDT, " + str(profit) + "% change)"
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
schedule.add_job(make_trade, 'cron', minute="00,05,10,15,20,25,30,35,40,45,50,55")
schedule.start()