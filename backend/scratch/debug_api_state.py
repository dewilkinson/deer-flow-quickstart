import requests
import json

URL = "http://localhost:8000/api/vli/active-state"

try:
    response = requests.get(URL)
    print(f"Status: {response.status_code}")
    data = response.json()
    print("Keys in response:", data.keys())
    if "chat_history" in data:
        print(f"Number of history items: {len(data['chat_history'])}")
        print("First item:", json.dumps(data["chat_history"][0], indent=2) if data["chat_history"] else "EMPTY")
    else:
        print("ERROR: chat_history missing from response!")
        print("Full response:", json.dumps(data, indent=2))
except Exception as e:
    print(f"FAILED: {e}")
