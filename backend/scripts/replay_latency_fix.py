import asyncio
from datetime import datetime
from src.utils.temporal import get_effective_now, reset_reference_time
from src.graph.nodes.common_vli import _instrument_temporal_context
from src.tools.finance import get_stock_quote

async def test_cross_node_sync():
    print("--- VLI Cross-Node Temporal Sync Verification ---")
    
    # 1. Setup simulated state from Spine
    origin_dt = datetime(2019, 6, 30, 16, 0)
    state = {
        "metadata": {
            "replay_origin": origin_dt.isoformat()
        },
        "messages": []
    }
    
    # Ensure current context is clean
    # (ContextVar is usually clean in a new script, but let's be safe)
    print(f"Initial Effective Now: {get_effective_now()}")
    
    # 2. Simulate node transition to a Specialist
    print("\n--- Simulating Node Transition (Spine -> Specialist) ---")
    _instrument_temporal_context(state)
    
    effective_now = get_effective_now()
    print(f"Specialist Effective Now: {effective_now}")
    
    if effective_now == origin_dt:
        print("SUCCESS: Specialist node correctly inherited the Replay Origin from state metadata.")
    else:
        print(f"FAILED: Specialist node is still at {effective_now}")
        return

    # 3. Verify Tool Execution in this synchronized context
    print("\n--- Verifying Tool Execution in Shadow Context ---")
    try:
        quote = await get_stock_quote.ainvoke({"ticker": "NVDA"})
        print(f"NVDA 2019 Quote: {quote}")
        
        from src.tools.finance import get_sortino_ratio
        sortino = await get_sortino_ratio.ainvoke({"ticker": "NVDA"})
        print(f"NVDA 2019 Sortino: {sortino}")
        
        if "Sortino Ratio (NVDA):" in sortino and "198." in str(quote.get("price")):
            print("SUCCESS: Both Quote and Sortino tools are synchronized to 2019.")
        else:
            print("FAILED: One or more tools failed to synchronize.")
    except Exception as e:
        print(f"CRASHED: {e}")

    # 4. Verify SMC Analysis in Shadow Context
    print("\n--- Verifying SMC Analysis in Shadow Context ---")
    try:
        from src.tools.finance import run_smc_analysis
        smc_res = await run_smc_analysis.ainvoke({"ticker": "NVDA", "interval": "1d", "lookback_days": 100})
        # Save to file to avoid terminal encoding issues
        with open("smc_debug.txt", "w", encoding="utf-8") as f:
            f.write(smc_res)
        print("SMC Result saved to smc_debug.txt (UTF-8)")
        if "Market Structure" in smc_res or "BOS" in smc_res:
            print("SUCCESS: SMC tool identified structural pivots in the historical data.")
        else:
            print("WARNING: SMC tool returned data, but no structural pivots were found.")
    except Exception as e:
        print(f"CRASHED: {e}")

if __name__ == "__main__":
    asyncio.run(test_cross_node_sync())
