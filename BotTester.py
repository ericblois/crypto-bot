import numpy as np
import pandas as pd
import random
import multiprocessing as mp
import time
import sys

#dataframe = pd.read_csv("./ETHDATA/ETH_USD_1h.csv")
dataframe = pd.read_csv("./FTX_BTC_USD_1m.csv")
dataframe = dataframe[["close", "96h-MA", "48h-MA", "24h-MA", "12h-MA", "6h-MA", "3h-MA", "%96h-MA", "%48h-MA", "%24h-MA", "%12h-MA", "%6h-MA", "%3h-MA", "Volume BTC", "high", "low"]]
data_vector = np.flipud(dataframe.to_numpy(dtype=np.float32))
length = np.shape(data_vector)[0]

START_BALANCE = 100


def run_random_day(rand_day, bot_values, hold_values, bot_to_hold_ratios, all_trade_profits, all_trade_losses):
    # --- VALUE VARIABLES ---

    balance = START_BALANCE
    crypto = 0
    value = balance

    # --- TRIGGER VARIABLES ---

    bought = False
    buy_trig = False
    sell_trig = False
    buy_trig = False
    sell_trig = False
    stop_loss = 0.02
    take_profit = 0.02

    # --- PRICE/PROFIT VARIABLES ---

    buy_price = 0
    sell_price = 0
    buy_value = 0
    profit_total = 0
    profit_count = 0
    loss_total = 0
    trans_count = 0
    start_price = 0
    end_price = 0
    stop_count = 0

    # --- OTHERS ---

    BUY_RATIO = 0.95
    SELL_RATIO = 0.95
    FEE_RATIO = 0.99981
    prev = []
    tr_prev = []
    long_gain_rma = 0
    long_loss_rma = 0
    short_gain_rma = 0
    short_loss_rma = 0
    long_ema = data_vector[rand_day - 1 * 1440][0]
    short_ema = data_vector[rand_day - 1 * 1440][0]
    last_price = 1
    time_since_buy = 0
    short = False

    for i, row in enumerate(data_vector[rand_day - 1 * 1440:rand_day]):
        '''
        vol = row[13]
        MA_3 = row[6]
        MA_6 = row[5]
        MA_12 = row[4]
        MA_24 = row[3]
        MA_48 = row[2]
        MA_96 = row[1]
        change_3 = row[12]
        change_6 = row[11]
        change_12 = row[10]
        change_24 = row[9]
        change_48 = row[8]
        change_96 = row[7]
        '''
        price = row[0]
        high = row[14]
        low = row[15]

        if i == 0:
            start_price = price
        end_price = price

        if bought:
            time_since_buy += 1

        # Get previous num close prices (from most recent to least recent in list)
        num = 30

        if len(prev) >= num + 1:
            prev.pop(num)
            prev.insert(0, price)
        else:
            prev.insert(0, price)

        # --- EMA Calculation ---

        long_ema_period = 26
        short_ema_period = 12
        ema_smoothing = 2
        long_ema = price*(ema_smoothing/(1 + long_ema_period)) + long_ema * (1 - (ema_smoothing/(1 + long_ema_period)))
        short_ema = price * (ema_smoothing / (1 + short_ema_period)) + short_ema * (
                    1 - (ema_smoothing / (1 + short_ema_period)))

        # --- MACD Calculation ---

        macd = long_ema - short_ema

        # --- RSI Calculations ---

        rsi_long_period = 30
        rsi_short_period = 15

        last_change = (price - last_price) / last_price
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

        # --- Changes ---

        if len(prev) <= num:
            continue

        changes = [(value - prev[i + 1]) / prev[i + 1] for i, value in enumerate(prev[:30])]
        change_MA = np.mean(changes)

        gains = []
        losses = []

        for change in changes:
            if change > 0:
                gains.append(change)
            elif change < 0:
                losses.append(change)

        # --- Bollinger Bands Calculations ---

        bb_period = 20
        bb_prev = prev[:bb_period]
        bb_std = np.std(bb_prev)
        # 20-day MA
        MA_band = np.mean(bb_prev)
        bb_upper_band = MA_band + 2 * bb_std
        bb_lower_band = MA_band - 2 * bb_std

        # --- ATR Calculations ---

        atr_period = 15
        # TR uses this interval's high and low, as well as last interval's close price
        tr_value = max([high - low, high - last_price, last_price - low])
        if len(tr_prev) == 0:
            tr_prev = prev[:atr_period]
        elif len(tr_prev) >= atr_period:
            tr_prev.pop(atr_period - 1)
            tr_prev.insert(0, tr_value)
        # Get ATR
        atr_value = np.mean(tr_prev)

        # --- Supertrend Calculations ---

        st_multi = 0.25
        st_upper_band = (max(prev[:atr_period]) + min(prev[:atr_period])) / 2 + st_multi * atr_value
        st_lower_band = (max(prev[:atr_period]) + min(prev[:atr_period])) / 2 - st_multi * atr_value
        # print("low: " + str(st_lower_band) + " high: " + str(st_upper_band) + " price: " + str(price))

        # --- TRIGGERS ---

        # Buys
        if not bought and not buy_trig and (long_rsi <= 31 and short_rsi <= 22 and (long_ema - price)/price*100 >= 0.89 and (short_ema - price)/price*100 >= 0.64 and (bb_lower_band - price)/price*100 >= 0):
            buy_trig = True
            short = False
        elif not bought and not buy_trig and (long_rsi >= 69 and short_rsi >= 77 and (long_ema - price)/price*100 <= -0.70 and (short_ema - price)/price*100 <= -0.50 and (bb_upper_band - price)/price*100 <= 0):
            buy_trig = True
            short = True
        # Sells
        elif bought and not short and (price - buy_price) / buy_price >= take_profit:
            sell_trig = True
        elif bought and short and (price - buy_price) / buy_price <= -take_profit:
            sell_trig = True

        # --- BUY CRYPTO --

        if (buy_trig and not short and price > last_price) or (buy_trig and short and price < last_price):
            # Keep track of balances and prices
            buy_price = price
            buy_value = balance + crypto * price
            crypto += ((balance * BUY_RATIO) / price) * FEE_RATIO
            balance -= balance * BUY_RATIO
            # Set trigger variables
            bought = True
            buy_trig = False
            time_since_buy = 0

            # --- STOP LOSS AND TAKE PROFIT ---

            stop_loss = (1 * atr_value) / price
            stop_loss = 0.01
            take_profit = (1.5 * stop_loss)
            #print(take_profit)
            # print("BUY $: " + str(buy_price))

        # --- SELL CRYPTO ---

        elif sell_trig or (bought and ((not short and (price - buy_price) / buy_price <= -stop_loss) or (short and (price - buy_price) / buy_price >= stop_loss))):
            if (bought and not short and price / buy_price <= 1 - stop_loss) or (
                    bought and short and price / buy_price >= 1 + stop_loss):
                stop_count += 1
            # Keep track of balances and prices
            sell_price = price
            if not short:
                balance += (crypto * price) * SELL_RATIO * FEE_RATIO
            else:
                pseudo_price = 2*buy_price - price
                balance += (crypto * pseudo_price) * SELL_RATIO * FEE_RATIO
            crypto -= crypto * SELL_RATIO
            sell_value = balance + crypto * price
            # Set trigger variables
            bought = False
            sell_trig = False
            # Calculate profits
            profit = (sell_value - buy_value) / buy_value * 100
            if profit >= 0:
                profit_count += 1
                profit_total += profit
                all_trade_profits.append(profit)
            elif profit < 0:
                loss_total += profit
                all_trade_losses.append(profit)
            trans_count += 1
            # print("SELL $: " + str(sell_price) + " | PROFIT: " + str(round((sell_value - buy_value) / buy_value * 100, 3)) + "% | VALUE: " + str(sell_value))
        # Keep track of last price and RSI
        last_price = price

    # --- END OF DAY CALCULATIONS ---

    # If still holding crypto, add another trade to total
    if bought:
        if not short:
            balance += (crypto * price) * SELL_RATIO * FEE_RATIO
        else:
            pseudo_price = 2*buy_price - price
            balance += (crypto * pseudo_price) * SELL_RATIO * FEE_RATIO
        crypto -= crypto * SELL_RATIO
        sell_value = balance + crypto * end_price
        profit = (sell_value - buy_value) / buy_value * 100
        if profit >= 0:
            profit_count += 1
            profit_total += profit
            all_trade_profits.append(profit)
        elif profit < 0:
            loss_total += profit
            all_trade_losses.append(profit)
        trans_count += 1

    # Determine wins
    day_value = end_price * crypto + balance
    # Keep track of all days' results
    bot_values.append(day_value)
    hold_value = end_price / start_price * 100
    hold_values.append(hold_value)
    # Compare to holding crypto from start to end
    bot_to_hold_ratio = (day_value - hold_value) / hold_value * 100
    bot_to_hold_ratios.append(bot_to_hold_ratio)

    '''
    print("Final:\nBalance: " + str(balance)
          + "\nCrypto($): " + str(crypto * row[0])
          + "\nTotal value: " + str(row[0] * crypto + balance)
          + "\nAVG Profit: " + str(round((profit_total + 1) / (profit_count + 1), 3))
          + "%\nAVG Loss: " + str(round((loss_total + 1) / (loss_count + 1), 3))
          + "%\nWins: " + str(profit_count) + "/" + str(trans_count) + " (" + str(round(profit_count / trans_count * 100, 2)) + "%)"
          + "\nBot Change: " + str(round(day_value, 2))
          + "%\nHold Change: " + str(round(hold_value, 2))
          + "%\nRatio vs Hold: " + str(ratio_hold)
          + "%\n-----")

    if (k + 1) % 10 == 0:
        print(k + 1)
    '''
    result_string = ""
    if trans_count == 0:
        result_string = "# Trades: 0 Win %: 0"
    else:
        # result_string = "# Trades: " + str(trans_count) + " Win %: " + str(round((profit_count)/(trans_count)*100, 2)) + " | Final Balance: " + str(day_value)
        result_string = "# Trades: " + str(trans_count) + " Stops: " + str(stop_count) + " Win %: " + str(
            round((profit_count) / (trans_count) * 100, 2))
    print(result_string)

if __name__ == "__main__":

    manager = mp.Manager()

    BOT_VALUES = manager.list()
    HOLD_VALUES = manager.list()
    BOT_TO_HOLD_RATIOS = manager.list()
    ALL_TRADE_PROFITS = manager.list()
    ALL_TRADE_LOSSES = manager.list()

    rand_days = [random.randint(length - 6 * 20160, length) for k in range(300)]

    start_time = time.time()
    '''
    for day in rand_days:
        run_random_day(day)
    '''
    pool = mp.Pool(mp.cpu_count())
    # Test all bots
    test_results = [pool.apply_async(run_random_day, args=(day, BOT_VALUES, HOLD_VALUES, BOT_TO_HOLD_RATIOS, ALL_TRADE_PROFITS, ALL_TRADE_LOSSES)) for day in rand_days]
    # Wait for all async processes to finish
    [result.wait() for result in test_results]
    # Get all bots and scores
    final_results = [result.get() for result in test_results]

    print("------\nTime taken: " + str(round(time.time() - start_time, 2)) + " seconds")

    ROUND_COUNT = len(BOT_VALUES)
    WIN_COUNT = 0
    for val in BOT_VALUES:
        if val > START_BALANCE:
            WIN_COUNT += 1

    median_bot_value = np.median(BOT_VALUES)
    mean_bot_value = np.mean(BOT_VALUES)
    std_bot_value = np.std(BOT_VALUES)
    median_hold_change = np.median(HOLD_VALUES)
    median_bot_to_hold_ratio = np.median(BOT_TO_HOLD_RATIOS)
    print("------\nMedian Bot Value: " + str(round(median_bot_value, 2)) + "% | Mean Bot Value: " + str(round(mean_bot_value, 2)) + "% | High: " + str(max(BOT_VALUES)) + "% | Low: " + str(min(BOT_VALUES)) + "% | STD: " + str(np.std(BOT_VALUES))
        + "\nMedian Hold Value: " + str(round(median_hold_change, 2)) + "% | High: " + str(max(HOLD_VALUES)) + "% | Low: " + str(min(HOLD_VALUES)) + "% | STD: " + str(np.std(HOLD_VALUES))
        + "\nMedian Ratio vs Hold: " + str(median_bot_to_hold_ratio)
        + "%\nWins: " + str(WIN_COUNT) + "/" + str(ROUND_COUNT) + " (" + str(round(WIN_COUNT / ROUND_COUNT * 100, 2)) + "%)"
        + "\n-----"
        + "\nMean Trade Profit: " + str(round(np.mean(ALL_TRADE_PROFITS), 3))
        + "\nMean Trade Losses: " + str(round(np.mean(ALL_TRADE_LOSSES), 3))
        + "\nMedian Trade Profit: " + str(round(np.median(ALL_TRADE_PROFITS), 3))
        + "\nMedian Trade Losses: " + str(round(np.median(ALL_TRADE_LOSSES), 3))
        + "\nTrade Win Rate: " + str(round((len(ALL_TRADE_PROFITS)/(len(ALL_TRADE_PROFITS) + len(ALL_TRADE_LOSSES)))*100, 2)) + "%")

    pool.close()
    pool.join()