import asyncio
import os
import sys

# Setup paths to allow importing from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.server.app import _invoke_vli_agent

async def main():
    print("Testing _invoke_vli_agent with raw_data_mode=True without a specific ticker")
    res, state = await _invoke_vli_agent("Tell me about the stock market", raw_data_mode=True)
    print("Result of _invoke_vli_agent:")
    print(res)

if __name__ == "__main__":
    asyncio.run(main())
