import asyncio
import os
import sys

# Ensure backend/src is in pythonpath
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import finance tool first, it seems to handle its own imports fine when run as an entrypoint
from src.tools.finance import simulate_cache_volatility
from src.services.datastore import DatastoreManager
from src.services.heat_manager import HeatManager
from src.tools.shared_storage import GLOBAL_CONTEXT

async def main():
    print("Populating cache...")
    DatastoreManager.ensure_worker_started()
    await simulate_cache_volatility.ainvoke({"num_high": 1, "num_moderate": 1, "num_inactive": 1})
    
    print("\nState after population:")
    print(f"Heat Map items: {len(HeatManager.get_heat_map())}")
    print(f"Cached tickers (GLOBAL): {len(GLOBAL_CONTEXT.get('cached_tickers', set()))}")
    print(f"Ticker metadata (GLOBAL): {len(GLOBAL_CONTEXT.get('ticker_metadata', {}))}")
    
    print("\nInvalidating specific ticker HIGH_0...")
    DatastoreManager.invalidate_cache("HIGH_0")
    
    print("\nState after specific invalidation:")
    print(f"Heat Map items: {len(HeatManager.get_heat_map())}")
    print(f"Cached tickers (GLOBAL): {len(GLOBAL_CONTEXT.get('cached_tickers', set()))}")
    print(f"Ticker metadata (GLOBAL): {len(GLOBAL_CONTEXT.get('ticker_metadata', {}))}")
    
    print("\nInvalidating all...")
    DatastoreManager.invalidate_cache()
    
    print("\nState after full invalidation:")
    print(f"Heat Map items: {len(HeatManager.get_heat_map())}")
    print(f"Cached tickers (GLOBAL): {len(GLOBAL_CONTEXT.get('cached_tickers', set()))}")
    print(f"Ticker metadata (GLOBAL): {len(GLOBAL_CONTEXT.get('ticker_metadata', {}))}")
    
if __name__ == "__main__":
    asyncio.run(main())
