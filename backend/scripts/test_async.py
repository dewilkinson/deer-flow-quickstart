import time
import requests
import json

URL = 'http://127.0.0.1:8000/api/vli/action-plan'
payload = {
    'text': '/vli analyze AAPL --RAW --BACKGROUND',
    'raw_data_mode': True,
    'direct_mode': False,
    'background_synthesis': True
}

print('Sending Async Request...')
t0 = time.time()
res = requests.post(URL, json=payload)
t1 = time.time()

print(f'\n[FastAPI Returned in {t1-t0:.2f}s!]')
print('Status Code:', res.status_code)
try:
    data = res.json()
    print('Response Keys:', data.keys())
    print('Action Status:', data.get('status'))
    # Ensure it's valid JSON payload inside 
    raw_payload = json.loads(data['response'])
    print('Raw Payload Extracted! Ticker:', raw_payload.get('ticker'))
except Exception as e:
    print('Error Parsing:', e)
