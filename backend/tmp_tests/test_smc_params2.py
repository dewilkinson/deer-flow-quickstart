import asyncio
import sys

sys.path.insert(0, './')
from src.tools.smc import get_smc_analysis

async def main():
    print("Testing 5d 1d...")
    res = await get_smc_analysis.coroutine(ticker="MSFT", period="5d", interval="1d")
    print(f"Len: {len(res)}, result: {res}")

if __name__ == "__main__":
    asyncio.run(main())
