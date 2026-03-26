import asyncio
import logging
from src.tools.macros import fetch_market_macros
from src.tools.finance import get_sharpe_ratio, get_sortino_ratio

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_primitives():
    print("\n" + "="*50)
    print("TESTING NEW MARKET PRIMITIVES")
    print("="*50)
    
    # 1. Test fetch_market_macros (First Pull - Deep Scan)
    print("\n--- 1. Testing fetch_market_macros (First Pull) ---")
    report1 = await fetch_market_macros.ainvoke({})
    print("Report fetched successfully.")
    print(f"Sample: {report1[:150]}...")
    
    # 2. Test fetch_market_macros (Second Pull - Cache Check)
    print("\n--- 2. Testing fetch_market_macros (Cache Verification) ---")
    report2 = await fetch_market_macros.ainvoke({})
    if "**[CACHED]**" in report2:
        print("PASS: [CACHED] tag found in second pull.")
    else:
        print("FAIL: [CACHED] tag missing from second pull within 15 mins.")
        
    # 3. Test get_sharpe_ratio (^TNX Fallback)
    print("\n--- 3. Testing get_sharpe_ratio (NVDA) ---")
    sharpe_report = await get_sharpe_ratio.ainvoke({"ticker": "NVDA"})
    print(sharpe_report)
    if "^TNX" in sharpe_report or "Risk-Free Rate" in sharpe_report:
        print("PASS: Sharpe report contains Risk-Free Rate context.")
    else:
        print("FAIL: Sharpe report missing Risk-Free context.")

    # 4. Test get_sortino_ratio (^TNX Fallback)
    print("\n--- 4. Testing get_sortino_ratio (MSFT) ---")
    sortino_report = await get_sortino_ratio.ainvoke({"ticker": "MSFT"})
    print(sortino_report)
    if "^TNX" in sortino_report or "Risk-Free Rate" in sortino_report:
        print("PASS: Sortino report contains Risk-Free Rate context.")
    else:
        print("FAIL: Sortino report missing Risk-Free context.")

if __name__ == "__main__":
    asyncio.run(test_primitives())
