import asyncio
import sys
import json

# Setup path
sys.path.insert(0, './')

async def verify():
    from src.tools.smc import get_smc_analysis
    
    print("Fetching high-fidelity SMC frame for NVDA...")
    data_str = await get_smc_analysis.ainvoke({'ticker': 'NVDA', 'period': '1y', 'interval': '1d'})
    
    # Verification
    if not data_str or "Error" in data_str:
        print(f"FAILED: {data_str}")
        return

    data = json.loads(data_str)
    size = len(data)
    
    # Check for structural markers (BOS, CHOCH, FVG, OB)
    bos_count = str(data).count("BOS")
    choch_count = str(data).count("CHOCH")
    fvg_count = str(data).count("fvg") # Case sensitive check based on smc.py
    ob_count = str(data).count("OB")

    print(f"Data Points: {size}")
    print(f"BOS Count: {bos_count}")
    print(f"CHOCH Count: {choch_count}")
    print(f"FVG Count: {fvg_count}")
    print(f"OB Count: {ob_count}")
    
    if size > 50 and (bos_count > 0 or choch_count > 0 or fvg_count > 0):
        print("RESULT: SUCCESS - High-fidelity sensible data verified.")
    else:
        print("RESULT: FAIL - Insufficient structural data.")

if __name__ == "__main__":
    asyncio.run(verify())
