import asyncio
import os
import sys

# Setup path and env
sys.path.insert(0, './')
# Ensure absolute imports resolve
sys.path.insert(0, os.getcwd())

os.environ["COBALT_AI_ON"] = "True"
os.environ["VLI_DEBUG_MODE"] = "True"

from src.server.app import _invoke_vli_agent
from src.services.datastore import DatastoreManager

async def verify():
    symbols = ["AAPL", "MSFT"]
    print(f"Verifying Stability for {symbols}...")
    
    for sym in symbols:
        # Clear cache to ensure deep re-fetch
        DatastoreManager.get_history_cache().clear()
        print(f"Testing {sym} (Cold Fetch)...", end=" ", flush=True)
        try:
            # invoke_vli_agent returns (res, final_state)
            res, state = await _invoke_vli_agent(
                text=f"Run a full SMC analysis for {sym}.",
                raw_data_mode=False
            )
            title = state.get("current_plan").title if state.get('current_plan') else 'Missing Plan'
            print(f"PASS | Plan: {title}")
        except Exception as e:
            print(f"FAIL | Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify())
