import asyncio
import httpx
import os

API_URL = "http://127.0.0.1:8000/api/vli/action-plan"
ARTIFACTS_DIR = os.path.join(os.getcwd(), "data", "artifacts")

async def test_symbol_phase1(client: httpx.AsyncClient, symbol: str):
    print(f"\n[{symbol}] Phase 1: Fetching initial raw data (--RAW)")
    resp1 = await client.post(API_URL, json={
        "text": f"Get {symbol} SMC --RAW",
        "raw_data_mode": True,
        "background_synthesis": False,
        "is_action_plan": False
    })
    
    if resp1.status_code == 200:
        if os.path.exists(os.path.join(ARTIFACTS_DIR, f"{symbol}.json")):
            print(f"[{symbol}] Artifact cached.")
        else:
            print(f"[{symbol}] ERROR: Artifact missing!")
    else:
        print(f"[{symbol}] Phase 1 Failed: {resp1.status_code}")

async def test_symbol_phase2(client: httpx.AsyncClient, symbol: str, follow_up: str):
    print(f"\n[{symbol}] Phase 2: Sending follow-up request ({follow_up})")
    resp2 = await client.post(API_URL, json={
        "text": follow_up,
        "raw_data_mode": False,
        "background_synthesis": False,
        "is_action_plan": False
    })
    
    if resp2.status_code == 200:
        print(f"[{symbol}] Phase 2 Success.")
    else:
        print(f"[{symbol}] Phase 2 Failed: {resp2.status_code}")

async def main():
    print("=== Automated VLI Context Retention Test ===")
    
    if os.path.exists(ARTIFACTS_DIR):
        for f in os.listdir(ARTIFACTS_DIR):
            os.remove(os.path.join(ARTIFACTS_DIR, f))
            
    print("Cleared existing artifacts.")
    
    symbols_and_followups = [
        ("NVDA", "Analyze NVDA using an EMA indicator. Calculate the 9, 13, 50, 250 lookback on the 4h chart. Display a table with the results for the last 50 candles."),
        ("AAPL", "Calculate ATR on AAPL."),
        ("MSFT", "Provide a CVD chart update on MSFT."),
        ("TSLA", "Analyze TSLA and look at order blocks."),
        ("AMD", "Set exit positions on AMD."),
        ("META", "Use trend analyzer on META.")
    ]
    
    import random

    async with httpx.AsyncClient(timeout=300.0) as client:
        await client.post("http://127.0.0.1:8000/api/vli/reset")
        
        # Phase 1: All RAW tasks sequentially
        for symbol, _ in symbols_and_followups:
            await test_symbol_phase1(client, symbol)
            await asyncio.sleep(2)
            
        # Shuffle for Phase 2
        random.shuffle(symbols_and_followups)
        print("\n--- Starting Randomized Follow-ups ---")
        
        # Phase 2: Analyis Tasks 
        for symbol, followup in symbols_and_followups:
            await test_symbol_phase2(client, symbol, followup)
            await asyncio.sleep(2)
            
    print("\n=== Test Sequence Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
