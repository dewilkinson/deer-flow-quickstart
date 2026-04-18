import pandas as pd
from datetime import datetime
from src.tools.finance import _bucket_sparkline_data

df = pd.DataFrame({'Close': [100, 101, 102, 103, 104]}, index=pd.date_range('2026-04-17 09:30', periods=5, freq='30min'))
print('Scenario 1: End at 11:30 AM')
print(_bucket_sparkline_data(df, datetime.now(), 104, 20, 390))
