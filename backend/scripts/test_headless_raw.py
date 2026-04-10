import asyncio
import os
import sys

# Setup paths to allow importing from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.server.app import _invoke_vli_agent
from src.tools.finance import get_raw_smc_tables

async def main():
    print("Testing get_raw_smc_tables")
    res = await get_raw_smc_tables("AAPL")
    print("Result of get_raw_smc_tables:", res[:200])

    print("Testing _invoke_vli_agent with raw_data_mode=True")
    res, state = await _invoke_vli_agent("AAPL", raw_data_mode=True)
    print("Result of _invoke_vli_agent:", res[:200])

if __name__ == "__main__":
    asyncio.run(main())
