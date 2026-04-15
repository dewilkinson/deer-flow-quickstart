import asyncio
import os
import sys

# Ensure backend/src is in pythonpath
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tools.macros import fetch_market_macros

async def main():
    print("Testing fetch_market_macros...")
    try:
        res = await fetch_market_macros.ainvoke({})
        print("Result:")
        print(res)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
