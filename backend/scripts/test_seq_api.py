import httpx
import time
import pprint

def test_api():
    print("Testing APA...")
    start = time.time()
    try:
        r1 = httpx.post("http://127.0.0.1:8000/api/vli/action-plan", json={"text": "Analyze APA"}, timeout=65.0)
        print(f"APA Time: {time.time() - start:.2f}s")
        print("APA Status:", r1.json().get("status"))
        print("APA Report Length:", len(r1.json().get("response", "")))
    except Exception as e:
        print(f"APA Failed: {e}")

    print("\nTesting ETHUSDT...")
    start = time.time()
    try:
        r2 = httpx.post("http://127.0.0.1:8000/api/vli/action-plan", json={"text": "Analyze ETHUSDT"}, timeout=65.0)
        print(f"ETHUSDT Time: {time.time() - start:.2f}s")
        print("ETHUSDT Status:", r2.json().get("status"))
        print("ETHUSDT Report Length:", len(r2.json().get("response", "")))
    except Exception as e:
        print(f"ETHUSDT Failed: {e}")

if __name__ == "__main__":
    test_api()
