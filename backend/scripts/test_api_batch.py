import asyncio
import httpx
import time
import os
import sys

SYMBOLS = ["APA", "ETHUSDT", "AAPL", "MSFT", "BTCUSDT"]
API_BASE = "http://127.0.0.1:8000/api/vli"

async def test_symbol(client, symbol, state):
    print(f"Testing {symbol}...")
    start_time = time.time()
    
    try:
        response = await client.post(
            f"{API_BASE}/action-plan",
            json={"text": f"Analyze {symbol}"},
            timeout=80.0
        )
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                report = data.get("response", str(data))
                if "report" in data:
                    report = data["report"]
            else:
                 report = str(data)
            
            if ("Apex Execution Summary" in report or "###" in report) and len(report) > 50:
                print(f"[{symbol}] PASSED in {duration:.2f}s")
                state['results'].append((symbol, "PASSED", f"{duration:.2f}s"))
            else:
                print(f"[{symbol}] FAILED (Short/Invalid Report) in {duration:.2f}s")
                state['results'].append((symbol, f"FAILED (Short/Invalid Report)", f"{duration:.2f}s"))
                state['errors'].append(f"{symbol} Output:\n{report[:500]}")
        else:
             print(f"[{symbol}] FAILED (HTTP {response.status_code}) in {duration:.2f}s")
             state['results'].append((symbol, f"FAILED (HTTP {response.status_code})", f"{duration:.2f}s"))
    except httpx.ReadTimeout:
         duration = time.time() - start_time
         print(f"[{symbol}] FAILED (TIMEOUT) in {duration:.2f}s")
         state['results'].append((symbol, "FAILED (TIMEOUT)", f"{duration:.2f}s"))
    except Exception as e:
         duration = time.time() - start_time
         print(f"[{symbol}] FAILED ({str(e)}) in {duration:.2f}s")
         state['results'].append((symbol, f"FAILED ({str(e)})", f"{duration:.2f}s"))

async def main():
    state = {'results': [], 'errors': []}
    async with httpx.AsyncClient() as client:
        for symbol in SYMBOLS:
            await test_symbol(client, symbol, state)
            await asyncio.sleep(2)
            
    print("\n" + "="*60 + "\n FINAL RESULTS\n" + "="*60)
    all_passed = True
    for sym, status, duration in state["results"]:
        if "FAILED" in status:
            print(f"- {sym}: [FAILED] {status} ({duration})")
            all_passed = False
        else:
             print(f"- {sym}: [PASSED] ({duration})")
            
    if state["errors"]:
         print("\n[ ERRORS DETECTED ]")
         for err in state["errors"]:
             print("-" * 40)
             print(err)
    
    if all_passed:
        print("\n>>> PIPELINE VERIFIED: All tested symbols returned comprehensive reports!")
        sys.exit(0)
    else:
        print("\n>>> PIPELINE FAILURE: Review the failed tests above.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
