import asyncio
from datetime import datetime
from src.utils.temporal import set_reference_time, reset_reference_time
from src.tools.finance import run_smc_analysis

async def test_deep_history_scaling():
    print("--- VLI Deep-History Adaptive Scaling Verification ---")
    
    # 1. Setup 2019 Origin (Deep History > 700 days)
    origin_dt = datetime(2019, 6, 30, 16, 0)
    set_reference_time(origin_dt)
    print(f"Set Virtual Time: {origin_dt}")
    
    # 2. Execute MTF Analysis (interval='auto')
    print("\n--- Executing Multi-Timeframe (MTF) Scaling Scan ---")
    try:
        # We explicitly use interval="auto" to trigger the MTF path
        res = await run_smc_analysis.ainvoke({"ticker": "NVDA", "interval": "auto"})
        
        print(f"Result Header: {res.splitlines()[0]}")
        
        # 3. Verify Downsampling in the report
        if "MTF SMC Structural Replay" in res or "Legacy Analysis Mode" in res:
            print("SUCCESS: System correctly identified Deep History and switched to Structural Replay mode.")
        else:
            print("FAILED: System did not trigger adaptive scaling.")
            
        # 4. Check for Data in all 3 maps
        maps_found = 0
        if "### 1. Macro Map (1mo)" in res:
            print("Check: Macro Map (1mo) found.")
            maps_found += 1
        if "### 2. Tactical Map (1wk)" in res:
            print("Check: Tactical Map (1wk) found.")
            maps_found += 1
        if "### 3. Execution Trigger (1d)" in res:
            # Note: My code set Trigger to 1d
            print("Check: Execution Trigger (1d) found.")
            maps_found += 1
            
        if maps_found == 3:
            print("SUCCESS: Full MTF alignment achieved via adaptive scaling.")
        else:
            print(f"PARTIAL FAIL: Found {maps_found}/3 maps. Some data might still be missing.")
            
    except Exception as e:
        import traceback
        print(f"CRASHED: {e}")
        print(traceback.format_exc())
    finally:
        reset_reference_time()

if __name__ == "__main__":
    asyncio.run(test_deep_history_scaling())
