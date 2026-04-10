import asyncio
import sys
import time

sys.path.insert(0, './')
from src.tools.finance import run_smc_analysis

async def main():
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "NFLX", "AMD", "INTC"]
    
    print("=" * 70)
    print(" SMC DEEP MTF PIPELINE PERFORMANCE BENCHMARK ")
    print("=" * 70)
    
    total_time = 0
    total_chars = 0
    
    header = f"{'Symbol':<8} | {'Latency':<8} | {'Size':<6} | {'Macro(1d)':<10} | {'Tact(1h)':<10} | {'Exec(5m)':<10}"
    print(header)
    print("-" * 70)
    
    for sym in symbols:
        start_time = time.perf_counter()
        try:
            # We call the tool that coordinates multiple timeframe queries internally
            res = await run_smc_analysis.coroutine(ticker=sym, interval="auto")
            elapsed = time.perf_counter() - start_time
            
            chars = len(res)
            total_time += elapsed
            total_chars += chars
            
            # Check for the existence of timeframe sections and OHLC data
            has_macro = "[OK]" if "Macro Map (1d)" in res and "OHLC" in res.split("Macro Map (1d)")[1].split("Tactical Map")[0] else "MISSING"
            has_tact = "[OK]" if "Tactical Map" in res and "OHLC" in res.split("Tactical Map")[1].split("Execution Trigger")[0] else "MISSING"
            
            # 5m segment might be missing 'Apex Authorization' but at least contains OHLC
            try:
                has_exec = "[OK]" if "Execution Trigger" in res and "OHLC" in res.split("Execution Trigger")[1] else "MISSING"
            except IndexError:
                has_exec = "MISSING"

            print(f"{sym:<8} | {elapsed:.2f}s   | {chars:<6} | {has_macro:<10} | {has_tact:<10} | {has_exec:<10}")
            
            # Print a quick snapshot of the first symbol to verify the data locally on the dev side
            if sym == "AAPL":
                with open("aapl_mtf_sample.md", "w", encoding="utf-8") as f:
                    f.write(res)
                    
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            print(f"{sym:<8} | {elapsed:.2f}s   | ERROR  | {str(e)[:30]}")
            
    print("-" * 70)
    print(f"AVERAGE LATENCY: {total_time / len(symbols):.2f}s")
    print(f"AVERAGE PAYLOAD: {total_chars / len(symbols):.0f} chars")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
