import asyncio
import sys
import os
import time
from datetime import datetime

# Add backend/src to path
sys.path.append(os.path.join(os.getcwd(), "backend"))
from src.tools.finance import get_stock_quote
from src.services.datastore import DatastoreManager

async def test_quote(ticker):
    print(f"\n--- Testing Ticker: {ticker} ---")
    start_time = time.time()
    try:
        # We test with use_fast_path=True which is the VLI default
        result = await get_stock_quote.func(ticker=ticker, use_fast_path=True)
        duration = time.time() - start_time
        print(f"Latency: {duration:.2f}s")
        if isinstance(result, dict):
            print(f"SUCCESS: {result.get('symbol')} -> ${result.get('price')} ({result.get('change', 0):+.2f}%)")
            if result.get('is_fast_fetch'):
                print("Path: FAST_FETCH (yfinance.fast_info)")
            elif result.get('is_cached'):
                print(f"Path: CACHE_HIT (Age unknown)")
            else:
                print("Path: BATCHED_FETCH (yfinance.history)")
        else:
            print(f"ERROR/FALLBACK: {result}")
    except Exception as e:
        print(f"CRITICAL EXCEPTION: {e}")

async def main():
    # Ensure datastore is up or at least mocked for local test
    # DatastoreManager relies on some env vars usually, but let's see if it works raw
    os.environ["VLI_MEMORY_MODE"] = "True" # Force memory mode if possible to avoid DB overhead for scratch test
    
    tickers = ["AAPL", "BTC", "ETH", "INVALID_TICKER_123"]
    
    print(f"Starting VLI Quote Diagnostic at {datetime.now()}")
    for t in tickers:
        await test_quote(t)
    
    print("\nDiagnostic Complete.")

if __name__ == "__main__":
    asyncio.run(main())
