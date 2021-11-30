import ftx
import time
import numpy as np

SYMBOL = "BNB"
# Length of intervals in minutes
INTERVAL = 1
# Number of historical prices to request
NUM_HIST_DATA = 10


API_STRINGS = open("FTX_API_Key", 'r').readlines()
for i, string in enumerate(API_STRINGS):
    API_STRINGS[i] = string.strip()

API_KEY = API_STRINGS[0]
API_SECRET = API_STRINGS[1]
ftx_client = ftx.FtxClient(api_key=API_KEY, api_secret=API_SECRET)

# Get historical data
now = time.time()
data = ftx_client.get_historical_data(SYMBOL + "/USD", INTERVAL * 60, limit=35, start_time=now - (NUM_HIST_DATA * INTERVAL * 60 + INTERVAL * 60), end_time=now)
# Make sure data is up to date
#while round(time.time()-5, -1)*1000 != data[len(data) - 1]['time']:
    #now = time.time()
    #data = ftx_client.get_historical_data(SYMBOL + "/USD", INTERVAL * 60, limit=35, start_time=now - (NUM_HIST_DATA * INTERVAL * 60 + INTERVAL * 60), end_time=now)
# Convert received data to list of close prices
hist_values = [value['close'] for value in data]
# Get rid of current price
prev = hist_values[:len(hist_values)-1]
print(prev)
hist = ftx_client.get_order_history()[0]['price']
print("--")
market = ftx_client.get_market("BNB/USDT")
print(market)
print(hist)
orders = ftx_client.get_open_orders()
print(orders)
orderbook = ftx_client.get_orderbook(SYMBOL + "/USD", 1)
trade_price = (orderbook['bids'][0][0] + orderbook['asks'][0][0])/2
print(trade_price)
balances = ftx_client.get_balances()
crypto_balance = None
for value in balances:
    if value['coin'] == "USDT":
        crypto_balance = float(value['free'])
print(crypto_balance)
'''
ftx_client.place_order(
    market=SYMBOL + "/USD",
    side="sell",
    price=2700,
    type="limit",
    size=1
)'''