import pandas as pd
import numpy as np

# Create sparse data with large time gaps to simulate overnight/weekends
dates = pd.date_range('2026-04-14 15:00', periods=60, freq='1min').tolist() + \
        pd.date_range('2026-04-17 09:30', periods=120, freq='1min').tolist()

df = pd.DataFrame({'Close': range(1, 181)}, index=dates)

target_data = df["Close"].dropna().sort_index()

# Get the last 390 active trading minutes (rows)
# If less than 390, it just takes whatever is there
recent_data = target_data.tail(390)

if recent_data.empty:
    print("EMPTY")
else:
    # Calculate indices to extract 20 evenly spaced points from these rows
    indices = np.linspace(0, len(recent_data) - 1, 20, dtype=int)
    values = recent_data.iloc[indices].tolist()
    print([round(v, 4) for v in values])
