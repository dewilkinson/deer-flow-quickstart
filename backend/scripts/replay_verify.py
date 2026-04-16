import asyncio
from datetime import datetime
import pandas as pd
from src.utils.temporal import parse_temporal_directive, set_reference_time, get_effective_now
from src.tools.finance import get_stock_quote

async def test_temporal_engine():
    print("--- VLI Replay Engine Verification ---")
    
    # 1. Test NL Parsing
    queries = [
        "How did SPY perform yesterday?",
        "What was the outlook on Wednesday?",
        "AAPL analysis for 2024-03-15",
        "run an smc analysis of NVDA for 30th June, 2019"
    ]
    
    for q in queries:
        dt = parse_temporal_directive(q)
        print(f"Query: '{q}' -> Resolved Date: {dt}")
        if not dt:
            print(f"FAILED: Could not parse '{q}'")

    # 2. Test Shadow Context Fetching
    print("\n--- Testing Shadow Context Fetching (AAPL 2024-03-15) ---")
    target_dt = datetime(2024, 3, 15, 16, 0)
    token = set_reference_time(target_dt)
    
    try:
        print(f"Effective Now: {get_effective_now()}")
        
        # This should trigger _fetch_replay_history internally
        quote = await get_stock_quote.ainvoke({"ticker": "AAPL", "use_fast_path": False})
        print(f"Replay Quote Result: {quote}")
        
        # Check cache segmentation
        from src.tools.shared_storage import history_cache
        print(f"Cache Keys: {list(history_cache.keys())}")
        
        # 3. Test Direct yfinance fetch in Replay Mode
        from src.tools.finance import _fetch_replay_history
        print("\n--- Direct yfinance Replay Fetch (AAPL 2024-03-15) ---")
        hist_data = await asyncio.to_thread(_fetch_replay_history, ["AAPL"], "1d", "1m", end_date=target_dt)
        if not hist_data.empty:
            print(f"Data Head:\n{hist_data.head(2)}")
            print(f"Data Tail:\n{hist_data.tail(2)}")
            # Handle MultiIndex or Flat Index
            if isinstance(hist_data.columns, pd.MultiIndex):
                typical_price = hist_data["AAPL"]["Close"].iloc[-1]
            else:
                typical_price = hist_data["Close"].iloc[-1]
            print(f"Typical Price: {typical_price}")
        else:
            print("FAILED: History fetch returned empty dataframe.")

    finally:
        pass # ContextVar is task-local, but in a script we're fine.

    # 4. Test SMC Analysis Replay
    from src.tools.finance import run_smc_analysis
    print("\n--- SMC Analysis Replay Benchmark (NVDA 2019-06-30) ---")
    target_smc_dt = datetime(2019, 6, 30, 0, 0)
    set_reference_time(target_smc_dt)
    
    start_smc = datetime.now()
    try:
        smc_res = await run_smc_analysis.ainvoke({"ticker": "NVDA", "interval": "1d", "lookback_days": 100})
        duration = (datetime.now() - start_smc).total_seconds()
        print(f"SMC Result Length: {len(str(smc_res))} chars")
        print(f"SMC Latency: {duration:.2f}s")
        if duration > 30:
            print("WARNING: High latency detected in SMC computation.")
    except Exception as e:
        print(f"FAILED: SMC Replay Analysis crashed: {e}")

if __name__ == "__main__":
    asyncio.run(test_temporal_engine())
