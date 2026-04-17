import os
import sys
import logging
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# Avoid circular imports or issues by just adding src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from src.tools.finance import _bucket_sparkline_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug")

tickers = ["SPY", "QQQ", "IWM", "DX-Y.NYB", "^VIX", "BTC-USD"]
ref_time = datetime.now() # Naive
print(f"Sampling sparklines ending at {ref_time}...")

data = yf.download(tickers, period="2d", interval="1m", prepost=True, group_by="ticker", progress=False)

for t in tickers:
    if t in data.columns.levels[0]:
        df = data[t] # Don't dropna yet, let _bucket_sparkline_data do it
        current_price = df.dropna(how="all").iloc[-1]["Close"]
        prices = _bucket_sparkline_data(df, ref_time, current_price, num_points=32, span_minutes=240)
        variance = max(prices) - min(prices)
        print(f"{t}: Points={len(prices)}, Variance={variance:.4f}, First={prices[0]}, Last={prices[-1]}")
        if variance == 0:
            print(f"  !!! FLAT LINE DETECTED for {t}")
    else:
        print(f"{t}: EMPTY DF")
