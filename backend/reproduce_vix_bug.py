import asyncio
from src.tools.finance import _normalize_ticker, _fetch_batch_history

async def test():
    t = "^VIX"
    norm = _normalize_ticker(t)
    print(f"Normalize('{t}') -> '{norm}'")
    
    # Simulate the audit tool call
    # _fetch_batch_history calls _normalize_ticker again
    try:
        data = _fetch_batch_history([norm], "1d", "1m")
        print("Fetch successful")
    except Exception as e:
        print(f"Fetch failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())
