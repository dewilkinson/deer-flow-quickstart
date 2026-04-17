import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug")

def _bucket_sparkline_data(df: pd.DataFrame, ref_time: datetime, current_price: float, num_points: int = 20, span_minutes: int = 390) -> list[float | None]:
    if df.empty:
        return [round(current_price, 4)] * num_points
    col = "Close" if "Close" in df.columns else "close"
    target_data = df[col]
    if isinstance(target_data, pd.DataFrame):
        target_data = target_data.iloc[:, 0]
    try:
        if getattr(df.index, 'tz', None) is not None:
            df.index = df.index.tz_convert('America/New_York').tz_localize(None)
        else:
            df.index = pd.to_datetime(df.index)
    except Exception as e:
        pass
    temp_series = target_data.sort_index()
    start_time = ref_time - timedelta(minutes=span_minutes)
    target_index = pd.date_range(start=start_time, end=ref_time, periods=num_points).round('s')
    values = []
    for i, target_time in enumerate(target_index):
        tt = target_time
        try:
            val = temp_series.asof(tt)
            if pd.isna(val): val = None
            values.append(val)
        except Exception as e:
            values.append(None)
    # Forward fill Nones if any
    last_val = current_price
    for i in range(len(values)):
        if values[i] is None:
            values[i] = last_val
        else:
            last_val = values[i]
    return [round(float(v), 4) if v is not None else 0.0 for v in values]

tickers = ["SPY", "QQQ", "IWM", "DX-Y.NYB", "^VIX", "BTC-USD"]
ref_time = datetime.now() # Naive
print(f"Sampling sparklines ending at {ref_time}...")

data = yf.download(tickers, period="2d", interval="1m", prepost=True, group_by="ticker", progress=False)

for t in tickers:
    if t in data.columns.levels[0]:
        df = data[t].dropna(how="all")
        if not df.empty:
            prices = _bucket_sparkline_data(df, ref_time, df.iloc[-1]["Close"], num_points=32, span_minutes=240)
            variance = max(prices) - min(prices)
            print(f"{t}: Points={len(prices)}, Variance={variance:.4f}, First={prices[0]}, Last={prices[-1]}")
            if variance == 0:
                print(f"  !!! FLAT LINE DETECTED for {t}")
        else:
            print(f"{t}: EMPTY DF")
