import asyncio
import sys
import os
import time
from datetime import datetime

# Add backend/src to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Bypass the @tool decorator by importing the underlying function directly if possible,
# or just redefine a minimal version for testing if the imports are too tangled.
# But let's try to use the actual code.

os.environ["VLI_CACHE_DISABLED"] = "True" # Force bypass of datastore logic

import yfinance

async def standalone_quote_test(ticker):
    print(f"\n[DIAGNOSTIC] Testing: {ticker}")
    start = time.time()
    try:
        # This is the 'Fast-Fetch' logic from finance.py:670
        t_obj = yfinance.Ticker(ticker)
        fast = t_obj.fast_info
        
        if fast is not None and hasattr(fast, "last_price") and fast.last_price:
            price = fast.last_price
            change = ((fast.last_price / fast.previous_close) - 1) * 100 if hasattr(fast, "previous_close") and fast.previous_close else 0.0
            duration = time.time() - start
            print(f"SUCCESS: {ticker} -> ${price:.2f} ({change:+.2f}%)")
            print(f"Latency: {duration:.2f}s")
        else:
            print(f"FAILURE: Fast-info returned empty/None for {ticker}")
            
    except Exception as e:
        print(f"EXCEPTION for {ticker}: {e}")

async def main():
    # Test common tickers that were causing issues
    test_tickers = ["AAPL", "BTC-USD", "ETH-USD", "SPY", "INVALID_TICKER_999"]
    
    print(f"Starting Standalone Quote Engine Diagnostic at {datetime.now()}")
    for t in test_tickers:
        await standalone_quote_test(t)
    print("\nDiagnostic Complete.")

if __name__ == "__main__":
    asyncio.run(main())
