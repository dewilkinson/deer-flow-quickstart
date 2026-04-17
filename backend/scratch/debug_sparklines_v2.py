import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

tickers = ["SPY", "QQQ", "IWM", "DX-Y.NYB", "^VIX", "^TNX", "CL=F", "BTC-USD"]
print(f"Testing 1m data fetch for {tickers}...")

data = yf.download(tickers, period="2d", interval="1m", prepost=True, group_by="ticker", progress=False)

for t in tickers:
    if t in data.columns.levels[0]:
        df = data[t].dropna(how="all")
        if not df.empty:
            last_price = df.iloc[-1]["Close"]
            print(f"{t}: Last Price={last_price:.2f}. Range: {df['Close'].min():.2f} - {df['Close'].max():.2f}")
        else:
            print(f"{t}: EMPTY")
    else:
        print(f"{t}: NOT FOUND")
