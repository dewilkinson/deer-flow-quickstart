import asyncio
import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.tools.smc import get_smc_analysis

async def test_raw_smc():
    r_func = getattr(get_smc_analysis, "coroutine", getattr(get_smc_analysis, "func", None))
    print("[DIAGNOSTIC] Fetching RAW SMC JSON Payload for MSFT...")
    try:
        # We specify the default period and interval
        res = await r_func(ticker="MSFT", period="60d", interval="1d")
        
        # Determine size and peek first record
        parsed = json.loads(res)
        print(f"[SUCCESS] Payload returned {len(parsed)} records.")
        print(f"[PEEK FIRST CANDLE]: {json.dumps(parsed[0], indent=2)}")
        print(f"[PEEK LAST CANDLE]: {json.dumps(parsed[-1], indent=2)}")
        
        # Save to disk so we can see the full thing easily
        with open("msft_raw_smc.json", "w") as f:
            f.write(res)
            
    except Exception as e:
        print(f"[ERROR]: {e}")

if __name__ == "__main__":
    asyncio.run(test_raw_smc())
