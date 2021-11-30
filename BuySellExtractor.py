import numpy as np
import pandas as pd
import random
import multiprocessing as mp
import time
import sys

# Minimum change in price over maximum period (percentage as a decimal)
MIN_CHANGE = 0.005
# Number of intervals to check for high/low
SEARCH_RADIUS = 10

# Read CSV file into a data frame
data_df = pd.read_csv("./FTX_BTC_USD_1m.csv")
data_df = data_df[["close"]]
# Convert close data to a matrix (flipped vertically and reshaped to a list)
data_vector = np.flipud(data_df.to_numpy(dtype=np.float32))
data_vector = data_vector.reshape(-1,)
data_vector = data_vector[len(data_vector) - 90 * 1440:]
length = len(data_vector)

bought = False
# Last index at which a trade happened
last_index = 0
last_trade_price = data_vector[0]

# --- Indicator variables ---

# RSI variables
rsi_long_period = 30
rsi_short_period = 15
long_gain_rma = 0
long_loss_rma = 0
short_gain_rma = 0
short_loss_rma = 0
# EMA variables
long_ema = data_vector[0]
short_ema = data_vector[0]
ema_long_period = 26
ema_short_period = 12
ema_smoothing = 2
# Bollinger bands
bb_period = 20
# --- Dataframe columns

buy_df = pd.DataFrame(columns=(
    "close",
    "trade",
    "change",
    str(rsi_long_period) + "m_RSI",
    str(rsi_short_period) + "m_RSI",
    str(ema_long_period) + "m_EMA %",
    str(ema_short_period) + "m_EMA %",
    "MACD",
    str(bb_period) + "m_BB Upper %",
    str(bb_period) + "m_BB Lower %"
))
sell_df = buy_df.copy(deep=True)
'''
buy_df["close"] = []
buy_df["trade"] = ["None"] * length
buy_df["change"] = [0] * length
buy_df[str(rsi_long_period) + "m_RSI"] = [0] * length
buy_df[str(rsi_short_period) + "m_RSI"] = [0] * length
buy_df[str(ema_long_period) + "m_EMA"] = [0] * length
buy_df[str(ema_short_period) + "m_EMA"] = [0] * length
buy_df["MACD"] = [0] * length
buy_df[str(bb_period) + "m_BB Upper"] = [0] * length
buy_df[str(bb_period) + "m_BB Lower"] = [0] * length
'''
# Keep track of time
start_time = time.time()
current_time = -1
# Iterate through historical close prices
for index, price in enumerate(data_vector):
    if index % int(length / 100) == 0:
        #current_time = round(time.time() - start_time - 0.5)
        print('\r (' + str(int(index/int(length / 100))) + '%) Searching for trade positions...', end='')
    if index < SEARCH_RADIUS:
        continue
    did_trade = False
    row_values = [0] * 5
    # Get data around current interval
    surrounding_data = data_vector[index - SEARCH_RADIUS: index + SEARCH_RADIUS]
    # Check if not bought and current value is lowest within search radius
    if not bought and np.argmin(surrounding_data) == SEARCH_RADIUS:
        bought = True
        row_values[0:3] = [price, "Buy", (price - last_trade_price)/last_trade_price*100]
        #print((price - last_trade_price) / last_trade_price * 100)
        last_trade_price = price
        did_trade = True
    elif bought and np.argmax(surrounding_data) == SEARCH_RADIUS:
        bought = False
        row_values[0:3] = [price, "Sell", (price - last_trade_price)/last_trade_price*100]
        #print((price - last_trade_price) / last_trade_price * 100)
        last_trade_price = price
        did_trade = True

    # Calculate indicators

    # --- RSI Calculations ---

    last_change = price - data_vector[index - 1]
    rsi_gain = last_change if last_change > 0 else 0
    rsi_loss = abs(last_change) if last_change < 0 else 0
    # Long RMA's
    long_gain_rma = ((long_gain_rma * (rsi_long_period - 1)) + rsi_gain) / rsi_long_period
    long_loss_rma = ((long_loss_rma * (rsi_long_period - 1)) + rsi_loss) / rsi_long_period
    # Short RMA's
    short_gain_rma = ((short_gain_rma * (rsi_short_period - 1)) + rsi_gain) / rsi_short_period
    short_loss_rma = ((short_loss_rma * (rsi_short_period - 1)) + rsi_loss) / rsi_short_period

    long_rsi = 100 - (100 / (1 + long_gain_rma / (long_loss_rma + 0.0000000001)))
    short_rsi = 100 - (100 / (1 + short_gain_rma / (short_loss_rma + 0.0000000001)))

    # --- EMA Calculation ---

    long_ema = price * (ema_smoothing / (1 + ema_long_period)) + long_ema * (
            1 - (ema_smoothing / (1 + ema_long_period)))
    short_ema = price * (ema_smoothing / (1 + ema_short_period)) + short_ema * (
            1 - (ema_smoothing / (1 + ema_short_period)))

    if did_trade:

        row_values[3:5] = [long_rsi, short_rsi]

        # --- MACD Calculation ---

        macd = long_ema - short_ema

        row_values[5:8] = [(long_ema - price)/price*100, (short_ema - price)/price*100, macd]

        # --- Bollinger Bands Calculations ---

        bb_prev = data_vector[index - bb_period + 1: index+1]
        bb_std = np.std(bb_prev)
        # 20-day MA
        MA_band = np.mean(bb_prev)
        bb_upper_band = MA_band + 2 * bb_std
        bb_lower_band = MA_band - 2 * bb_std

        row_values[8:10] = [(bb_upper_band - price)/price*100, (bb_lower_band - price)/price*100]

        # Save row values in dataframe
        if bought:
            buy_df.loc[len(buy_df.index)] = row_values
        else:
            sell_df.loc[len(buy_df.index)] = row_values



buy_df.to_csv("BTC_BUY_10m_RADIUS.csv", index=False)
sell_df.to_csv("BTC_SELL_10m_RADIUS.csv", index=False)
print(buy_df.head)