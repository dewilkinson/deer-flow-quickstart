import yfinance
import asyncio
import time

async def test_yfinance():
    ticker = "AAPL"
    print(f"Testing yfinance for {ticker}...")
    start = time.time()
    try:
        t = yfinance.Ticker(ticker)
        fast = t.fast_info
        print(f"Latency: {time.time() - start:.2f}s")
        print(f"Price: {fast.last_price}")
        print(f"Previous Close: {fast.previous_close}")
    except Exception as e:
        print(f"YFINANCE ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_yfinance())
