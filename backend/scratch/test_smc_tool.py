import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')
from src.tools.finance import run_smc_analysis, get_stock_quote

async def test_smc():
    
    print("Testing get_stock_quote for NVDA...")
    quote = await get_stock_quote.ainvoke({"ticker": "NVDA"})
    print(quote)

    print("\nTesting run_smc_analysis for NVDA...")
    smc = await run_smc_analysis.ainvoke({"ticker": "NVDA", "timeframe": "1d"})
    print(str(smc)[:1000])

asyncio.run(test_smc())
