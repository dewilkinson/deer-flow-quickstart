import asyncio
import time
from importlib import import_module
from src.tools.finance import get_stock_quote, run_smc_analysis, get_symbol_history_data

async def main():
    ticker = "NVDA"
    print("Testing isolated tool latencies:")
    
    t0 = time.time()
    try:
        f = getattr(get_stock_quote, "coroutine", getattr(get_stock_quote, "func", None))
        res1 = await f(ticker=ticker) if asyncio.iscoroutinefunction(f) else f(ticker=ticker)
        t1 = time.time() - t0
        print(f"1. get_stock_quote() -> {t1:.2f}s")
    except BaseException as e:
        print(f"get_stock_quote failed: {e}")
        
    t0 = time.time()
    try:
        f = getattr(run_smc_analysis, "coroutine", getattr(run_smc_analysis, "func", None))
        res2 = await f(ticker=ticker, interval="auto") if asyncio.iscoroutinefunction(f) else f(ticker=ticker, interval="auto")
        t2 = time.time() - t0
        print(f"2. run_smc_analysis() -> {t2:.2f}s")
    except BaseException as e:
        print(f"run_smc_analysis failed: {e}")
        
    t0 = time.time()
    try:
        f = getattr(get_symbol_history_data, "coroutine", getattr(get_symbol_history_data, "func", None))
        res3 = await f(symbols=[ticker], period="1d", interval="1h") if asyncio.iscoroutinefunction(f) else f(symbols=[ticker], period="1d", interval="1h")
        t3 = time.time() - t0
        print(f"3. get_symbol_history_data() -> {t3:.2f}s")
    except BaseException as e:
        print(f"get_symbol_history_data failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
