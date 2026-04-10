import json
import requests
import textwrap

URL = 'http://127.0.0.1:8000/api/vli/action-plan'
payload = {'text': 'analyze MSFT --RAW', 'raw_data_mode': True, 'direct_mode': False}
try:
    r = requests.post(URL, json=payload, timeout=5)
    data = json.loads(r.json()['response'])
    print('Ticker:', data['ticker'])
    print('Timeframe:', data['timeframe'])
    bars = data['data']
    print('Total Bars:', len(bars))

    if len(bars) > 0:
        for i in [-7, -6, -5, -4, -3, -2, -1]:
            idx = len(bars) + i
            if idx >= 0:
                b=bars[idx]
                fvg = b.get('fair_value_gap', None)
                trend = b.get('trend', None)
                print(f"Date: {b['Date']}, Close: {b['close']:.2f}, Vol: {b['volume']}, FVG: {fvg}, Trend: {trend}")
        print("\nSUMMARY RECENT LOWS/HIGHS:")
        # Print basic swing info
        highs = [b['high'] for b in bars[-10:]]
        lows = [b['low'] for b in bars[-10:]]
        print(f"10-Day High: {max(highs):.2f}, 10-Day Low: {min(lows):.2f}")
except Exception as e:
    print('Fetch failed:', e)
