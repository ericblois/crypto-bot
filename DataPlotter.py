import numpy as np
import pandas as pd
import random
import multiprocessing as mp
import time
import sys

close_dataframe = pd.read_csv("./FTX_XRP_USD_1m.csv")
close_dataframe = close_dataframe[["close"]]
data_vector = np.flipud(close_dataframe.to_numpy(dtype=np.float32))
data_vector = data_vector.reshape(-1,)

buy_sell_df = pd.read_csv("SEARCH_5m_RADIUS.csv")

print(buy_sell_df.head)
