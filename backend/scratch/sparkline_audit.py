
import asyncio
import yfinance
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add parent dir to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tools.finance import _fetch_batch_history, _extract_ticker_data

async def audit_sparkline(ticker="SPY"):
    print(f"--- SPARKLINE FIDELITY AUDIT: {ticker} ---")
    now = datetime.now()
    print(f"Current Local Time: {now}")
    
    # 1. Fetch 5m data (1d window)
    print("Fetching 5m data from yfinance...")
    data_5m = _fetch_batch_history([ticker], period="1d", interval="5m")
    df = _extract_ticker_data(data_5m, ticker)
    
    if df.empty:
        print("Error: No data returned from yfinance.")
        return

    # 2. Replicate the new Temporal Bucketing logic
    col = "Close" if "Close" in df.columns else "close"
    df.index = pd.to_datetime(df.index).tz_localize(None).as_unit('ns')
    temp_series = df[col]
    
    # Use the last row price as the anchor (same as tool logic)
    anchor_price = float(df[col].iloc[-1])
    ref_time = now # In the tool this is get_effective_now()
    
    sparkline_values = []
    bucket_times = []
    
    for i in range(29, -1, -1):
        target_time = pd.Timestamp(ref_time - timedelta(minutes=i*5)).as_unit('ns')
        idx = temp_series.index.searchsorted(target_time, side='right')
        if idx > 0:
            val = temp_series.iloc[idx-1]
            if i == 0: val = anchor_price
            sparkline_values.append(float(val))
        else:
            sparkline_values.append(anchor_price)
        bucket_times.append(target_time)
    
    print(f"\nLast 30 Sparkline Samples (Temporal Bucketing Logic)")
    print(f"{'Sample':<10} | {'Target (Local)':<25} | {'Source Time':<25} | {'Value':<12}")
    print("-" * 80)
    
    for i, (bt, sv) in enumerate(zip(bucket_times, sparkline_values)):
        target_minutes_ago = (29 - i) * 5
        # Re-fetch the source time for display
        idx = temp_series.index.searchsorted(bt, side='right')
        source_time = str(temp_series.index[idx-1]) if idx > 0 else "ANCHOR"
        
        print(f"#{i:2} ({target_minutes_ago:3}m ago) | {bt.strftime('%H:%M:%S'):<25} | {source_time:<25} | {sv:<12.4f}")

    print("\n--- BAR INTERVAL AUDIT ---")
    if len(temp_series.index) > 1:
        diffs = pd.Series(temp_series.index).diff().dropna()
        avg_diff = diffs.mean()
        print(f"Average Bar Interval: {avg_diff}")
        print(f"Expected Bar Interval: 00:05:00")
        
    print("\nAudit Complete.")

if __name__ == "__main__":
    asyncio.run(audit_sparkline())
