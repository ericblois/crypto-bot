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

binance_client = Client(
    "Oe9hWnotHo6Z185qVjQpnZuGi91sUGXEBqbaTDqUXDQq4ejEyfaFEpjBt5jRKKPI",
    "tUQK6WSXwj8lrGZjPq7AyKQ0DYBA6uhWRXMg0J1xm99XFMRtqdSHIF3XycduYCf1"
)

# Multiplier/divisor for order prices
SYMBOL = "BNB"
NUM = 59
Q_ROUND = 4
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

buy_price = 0
bought = False
if crypto_balance >= 0.01:
    bought = True
start_cash = 1

def make_trade():
    time.sleep(0.5)
    global buy_price
    global bought
    global start_cash
    #Past 60 5-minute intervals
    hist_values = np.matrix(binance_client.get_historical_klines(SYMBOL + "USDT", Client.KLINE_INTERVAL_5MINUTE, "12 hours ago UTC"))
    # Get last 6 data points
    hist_values = hist_values[:,4].T.tolist()[0]
    hist_values = [float(value) for value in hist_values]
    while len(hist_values) != 144:
        hist_values = np.matrix(binance_client.get_historical_klines(SYMBOL + "USDT", Client.KLINE_INTERVAL_5MINUTE, "12 hours ago UTC"))
        hist_values = hist_values[:, 4].T.tolist()[0]
        hist_values = [float(value) for value in hist_values]
    # Get rid of most recent value (the one that is continuously changing)
    prev = hist_values[:len(hist_values)-1]
    # Get past n 48h-MA's
    averages_48 = []
    for i in range(47, len(prev)):
        MA48 = np.mean(prev[i - 47:i + 1])
        averages_48.append(MA48)
    # Get past n 24h-MA's
    averages_24 = []
    for i in range(23, len(prev)):
        MA24 = np.mean(prev[i - 23:i + 1])
        averages_24.append(MA24)
    # Get past n-1 24h-MA changes
    changes = []
    for i, avg in enumerate(averages_24):
        if i == 0:
            continue
        change = avg - averages_24[i - 1]
        changes.append(change)
    # Get past n-2 second differences
    sec_diffs = []
    for i, chng in enumerate(changes):
        if i == 0:
            continue
        sec_diff = chng - changes[i - 1]
        sec_diffs.append(sec_diff)
    # Get average of past NUM second differences
    curve = np.mean(sec_diffs[len(sec_diffs)-NUM:])
    #Get price
    price = hist_values[len(hist_values) - 1]

    # --- PRINT INFO ---

    info_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " | PRICE: " + str(price) + ", CHANGE CURVE: " + str(round(curve, 5))
    if bought:
        info_str += ", WAITING TO SELL"
    else:
        info_str += ", WAITING TO BUY"

    print(info_str)

    # ALWAYS round to 5 decimals
    if curve <= -0.001 and not bought:
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
            send_mail("TradeBot has bought " + SYMBOL, buy_str)
        except:
            buy_str = "Bought " + str(quantity) + SYMBOL
            print(str_cyn(buy_str))
            send_mail("TradeBot has bought " + SYMBOL, buy_str)

        #print(order)
    elif curve >= 0.001 and bought:
        balance = float(binance_client.get_asset_balance(asset=SYMBOL)['free'])
        balance -= math.pow(0.1, Q_ROUND)*0.5
        quantity = round(balance, Q_ROUND)

        # --- PLACE SELL ORDER ---

        bought = False
        #Format quantity string
        quantity_str = '{:0.0{}f}'.format(quantity, Q_ROUND)
        order = binance_client.order_market_sell(
            symbol=SYMBOL + 'USDT',
            quantity=quantity_str
        )
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
        if profit > 0:
            sell_str = "Sold " + str(quantity) + SYMBOL + " at price of " + str(sell_price) + " (BALANCE: " + str(
                usdt_balance) + "USDT, " + str(profit) + "% change)"
            print(str_grn(sell_str))
            send_mail("TradeBot has sold " + SYMBOL, sell_str)
        elif profit < 0:
            sell_str = "Sold " + str(quantity) + SYMBOL + " at price of " + str(sell_price) + " (BALANCE: " + str(
                usdt_balance) + "USDT, " + str(profit) + "% change)"
            print(str_red(sell_str))
            send_mail("TradeBot has sold " + SYMBOL, sell_str)
        else:
            sell_str = "Sold " + str(quantity) + SYMBOL + " at price of " + str(sell_price) + " (BALANCE: " + str(
                usdt_balance) + "USDT, " + str(profit) + "% change)"
            print(str_mag(sell_str))
            send_mail("TradeBot has sold " + SYMBOL, sell_str)
        #print(order)

#make_trade()
print("Bot started!")
schedule = BlockingScheduler()
#schedule.add_job(make_trade, 'interval', minutes=5)
schedule.add_job(make_trade, 'cron', minute="00,05,10,15,20,25,30,35,40,45,50,55")
schedule.start()