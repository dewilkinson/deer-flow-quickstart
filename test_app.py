import requests
try:
    print("Sending SMC Analysis for GOOGL to API...")
    res = requests.post('http://localhost:8000/api/vli/action-plan', json={'text': 'SMC Analysis for GOOGL'})
    print("STATUS:", res.status_code)
    print("CONTENT:", res.text)
except Exception as e:
    print("FATAL ERROR:", e)
