import numpy as np
import pandas as pd
import random
import sys

#dataframe = pd.read_csv("./ETHDATA/ETH_USD_1h.csv")
dataframe = pd.read_csv("./BNB_USD_1m.csv")
dataframe = dataframe[["close", "96h-MA", "48h-MA", "24h-MA", "12h-MA", "6h-MA", "3h-MA", "%96h-MA", "%48h-MA", "%24h-MA", "%12h-MA", "%6h-MA", "%3h-MA", "Volume BNB"]]
data_vector = np.flipud(dataframe.to_numpy(dtype=np.float32))
length = np.shape(data_vector)[0]

balance = 100
eth = 0
value = balance
BUY_AMOUNT = 10

bought = False
last_change = 0
last_vol = 0
buy_price = 0
peak_price = 0
sell_price = sys.float_info.max
low_price = sys.float_info.max
d_count = 0
i_count = 0
i = 0
last_value = 1
buy_amount = 0
prev = []
buy_count = 0
profit_total = 0
profit_count = 0
trans_count = 0
for i in range(1):
    #rand_week = random.randint(length - 12000, length - 6000)
    for i, row in enumerate(data_vector[length-6*20160:]):
        value = row[0] * eth + balance
        if buy_count == 0:
            BUY_AMOUNT = abs(0.1*balance)
        elif buy_count == 1:
            BUY_AMOUNT = abs(0.28 * balance)
        elif buy_count == 2:
            BUY_AMOUNT = abs(0.54 * balance)
        elif buy_count == 3:
            BUY_AMOUNT = abs(0.99 * balance)
        BUY_AMOUNT = abs(0.995 * balance)
        vol = row[13]
        MA_3 = row[6]
        MA_6 = row[5]
        MA_12 = row[4]
        MA_24 = row[3]
        MA_48 = row[2]
        MA_96 = row[1]
        change_3 = row[12]
        #change_4 = row[15]
        change_6 = row[11]
        change_12 = row[10]
        #change_18 = row[17]
        change_24 = row[9]
        change_48 = row[8]
        change_96 = row[7]
        change_avg = (change_12)
        price = row[0]
        #print(ratio/last_ratio)
        current = MA_6
        change = change_avg
        value = price
        num = 70

        high = 0
        low = 0
        if len(prev) >= num:
            high = max(prev)
            low = min(prev)
            prev.pop(num-1)
        prev.insert(0, value)

        #high = max(prev[int(len(prev)*0.75) - 1:])

        if len(prev) < num:
            continue

        diffs = []
        for i, value in enumerate(prev):
            if i == 0:
                continue
            diffs.append(prev[i-1] - value)
        sec_diff = sum(diffs)/(num - 1)

        # Buy
        if price/MA_48 <= 0.98 and not bought:
            balance -= BUY_AMOUNT
            eth += BUY_AMOUNT/row[0]
            buy_price = price
            buy_amount += BUY_AMOUNT
            low_price = sys.float_info.max
            bought = True
            buy_count += 1
            #print("BUY:\nPrice: " + str(price) + ", d_count: " + str(d_count))
            print("BUY: Price: " + str(price) + ", HIGH: " + str(high) + ", LOW: " + str(low) + ", " + str(prev))
        # Sell
        elif price/MA_48 >= 1.02 and bought:
            amount = eth*row[0]
            balance += amount
            eth = 0
            sell_price = price
            peak_price = 0
            bought = False
            buy_count = 0
            profit = (amount - buy_amount)/buy_amount*100
            buy_amount = 0
            profit_total += profit
            if profit > 0:
                profit_count += 1
            trans_count += 1
            print("SELL:\nPrice: " + str(price) + ", i_count: " + str(i_count) + ", balance: " + str(balance) + ", profit: " + str(round(profit, 2)) + "%")

        # Get the peak price since last buy
        if bought and current >= peak_price:
            peak_price = current
        elif not bought and current <= low_price:
            low_price = current

        last_change = change_6
        # Keep track of change streaks
        if change > 0:
            i_count += 1
            d_count = 0
        elif change < 0:
            d_count += 1
            i_count = 0
        # Print info about each day
        i += 1
        if i % 24 == 0:
            value_change = value - last_value
            if last_value == 0:
                last_value = 1
            #print("Day " + str(i / 24) + ":\nBalance: " + str(balance) + "\nEthereum($): " + str(eth*row[0]) + "\nTotal value: " + str(value) + "\nValue increase: " + str(round((value_change/abs(last_value))*100, 2)) + "%\n-----")
            last_value = value

    print("Final:\nBalance: " + str(balance) + "\nCrypto($): " + str(eth*row[0]) + "\nTotal value: " + str(row[0]*eth+balance) + "\nAVG Profit: " + str(round(profit_total/trans_count, 2)) + "%\nWins: " + str(profit_count) + "/" + str(trans_count) + " (" + str(round(profit_count/trans_count*100, 2)) + "%)" + "\n-----")
amount = eth*data_vector[length - 1, 0]
balance += amount
eth = 0