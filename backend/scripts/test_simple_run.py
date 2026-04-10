import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.tools.finance import run_smc_analysis

async def main():
    r_func = getattr(run_smc_analysis, "coroutine", getattr(run_smc_analysis, "func", None))
    res = await r_func(ticker="XRPUSDT", interval="auto")
    with open("smc_output.txt", "w", encoding="utf-8") as f:
        f.write(res)

if __name__ == "__main__":
    asyncio.run(main())
