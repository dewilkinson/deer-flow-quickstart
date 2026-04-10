import asyncio
import httpx
import time
import sys
import os

SYMBOLS = ["APA", "ETHUSDT", "AAPL", "MSFT", "BTCUSDT"]
API_BASE = "http://127.0.0.1:8000/api/vli"

async def fetch_telemetry(client, state):
    while state["running"]:
        try:
            resp = await client.get(f"{API_BASE}/active-state", timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                state["telemetry"] = data.get("telemetry_tail", "")[-2000:]
        except Exception:
            pass
        await asyncio.sleep(1)

async def test_symbol(client, symbol, state):
    state["current_symbol"] = symbol
    state["start_time"] = time.time()
    state["status"] = "Sending POST request..."
    
    try:
        response = await client.post(
            f"{API_BASE}/action-plan",
            json={"text": f"Analyze {symbol}"},
            timeout=80.0 # generous timeout for testing
        )
        duration = time.time() - state["start_time"]
        
        if response.status_code == 200:
            data = response.json()
            # Depending on app.py response format it could be {"response": "..."} or raw text
            if isinstance(data, dict):
                report = data.get("response", str(data))
                if "report" in data:
                    report = data["report"]
            else:
                 report = str(data)
            
            if ("Apex Execution Summary" in report or "###" in report) and len(report) > 50:
                state["results"].append((symbol, "PASSED", f"{duration:.2f}s"))
            else:
                state["results"].append((symbol, f"FAILED (Short/Invalid Report)", f"{duration:.2f}s"))
                state["errors"].append(f"{symbol} Output:\n{report[:500]}")
        else:
             state["results"].append((symbol, f"FAILED (HTTP {response.status_code})", f"{duration:.2f}s"))
    except httpx.ReadTimeout:
         duration = time.time() - state["start_time"]
         state["results"].append((symbol, "FAILED (TIMEOUT)", f"{duration:.2f}s"))
    except Exception as e:
         duration = time.time() - state["start_time"]
         state["results"].append((symbol, f"FAILED ({str(e)})", f"{duration:.2f}s"))
         
async def ui_loop(state):
    while state["running"]:
        # Clear screen and move cursor to top left
        sys.stdout.write("\033[2J\033[H")
        
        print("="*60)
        print(" VLI ANALYZE PIPELINE TEST DASHBOARD")
        print("="*60)
        
        print("\n[ TEST PROGRESS ]")
        for sym, status, duration in state["results"]:
            if "FAILED" in status:
                print(f"- {sym}: \033[91m{status} ({duration})\033[0m")
            else:
                print(f"- {sym}: \033[92m{status} ({duration})\033[0m")
        
        if state["current_symbol"]:
            elapsed = time.time() - state["start_time"]
            print(f"\n> Currently processing: {state['current_symbol']} ({elapsed:.1f}s / 80.0s max)")
            print(f"> Network Status: {state['status']}")
            print("\n[ LIVE TELEMETRY LOGS ]")
            lines = state["telemetry"].strip().split("\n")
            for line in lines[-15:]:
                print(f"  {line[:100]}")
        else:
            print("\n> Preparing to start...")
            
        sys.stdout.flush()
        await asyncio.sleep(0.5)

async def main():
    state = {
        "running": True,
        "results": [],
        "errors": [],
        "current_symbol": None,
        "start_time": 0,
        "status": "",
        "telemetry": "Fetching telemetry..."
    }
    
    async with httpx.AsyncClient() as client:
        telemetry_task = asyncio.create_task(fetch_telemetry(client, state))
        ui_task = asyncio.create_task(ui_loop(state))
        
        for symbol in SYMBOLS:
            await test_symbol(client, symbol, state)
            await asyncio.sleep(3) # Let telemetry and reset propagation breathe
        
        state["running"] = False
        await ui_task
        
        # Clear screen one last time for final output
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        
        print("="*60)
        print(" FINAL RESULTS")
        print("="*60)
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
    if sys.platform == "win32":
        # Enable VT100 ANSI sequences on Windows console
        os.system("") 
    asyncio.run(main())
