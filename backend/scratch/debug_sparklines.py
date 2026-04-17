import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

tickers = ["SPY", "QQQ", "IWM", "DX-Y.NYB", "^VIX", "^TNX", "CL=F", "BTC-USD"]
print(f"Testing 1m data fetch for {tickers}...")

data = yf.download(tickers, period="2d", interval="1m", prepost=True, group_by="ticker", progress=False)

for t in tickers:
    if t in data.columns.levels[0]:
        df = data[t].dropna(how="all")
        print(f"{t}: {len(df)} 1m rows. Last timestamp: {df.index.max() if not df.empty else 'N/A'}")
    else:
        print(f"{t}: NOT FOUND IN BATCH")
