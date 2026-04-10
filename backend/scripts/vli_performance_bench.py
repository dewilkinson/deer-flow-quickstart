import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from statistics import mean
from unittest.mock import patch

from colorama import Back, Fore, Style, init

# Initialize colorama for Windows support
init(autoreset=True)

# Ensure backend is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llms.llm import get_llm_by_type
from src.tools.finance import get_stock_quote, _DF_CACHE

# Setup logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("vli_bench")

# Constants for UI
PASS = f"{Style.BRIGHT}{Fore.WHITE}{Back.GREEN}  PASS  {Style.RESET_ALL}"
INFO = f"{Fore.CYAN}{Style.BRIGHT}[INFO]{Style.RESET_ALL}"
TEST = f"{Fore.MAGENTA}{Style.BRIGHT}[TEST]{Style.RESET_ALL}"
TIMER = f"{Fore.YELLOW}{Style.BRIGHT}[TIMER]{Style.RESET_ALL}"

SYMBOLS = ["AAPL"]

class VLIBenchmark:
    def __init__(self, model_type: str, model_name: str):
        self.model_type = model_type
        self.model_name = model_name
        self.results = []
        self.llm = get_llm_by_type(model_type)

    async def run_iteration(self, symbol: str):
        # 1. Start Iteration
        it_start = time.perf_counter()
        
        # --- STAGE 0: Cache Invalidation (FORCED) ---
        _DF_CACHE.clear()
        
        # --- STAGE 1: Decision/Orchestration (LLM) ---
        s1_start = time.perf_counter()
        # Simulate agentic decision: "Fetch the quote for ticker X"
        prompt = f"Fetch the current stock quote for {symbol}. Which tool should you use? (Reply ONLY with 'get_stock_quote')"
        await self.llm.ainvoke(prompt)
        s1_end = time.perf_counter()
        decision_ms = (s1_end - s1_start) * 1000

        # --- STAGE 2: Fetch/Tool Execution (PYTHON/NETWORK) ---
        s2_start = time.perf_counter()
        # [FIX] Use .ainvoke() for StructuredTool
        tool_result = await get_stock_quote.ainvoke({"ticker": symbol, "force_refresh": True})
        s2_end = time.perf_counter()
        fetch_ms = (s2_end - s2_start) * 1000

        # --- STAGE 3: Synthesis/Reporting (LLM) ---
        s3_start = time.perf_counter()
        # Interpreting the data
        synth_prompt = f"Summarize the following quote data for {symbol} into a 1-sentence summary: {tool_result}"
        await self.llm.ainvoke(synth_prompt)
        s3_end = time.perf_counter()
        synth_ms = (s3_end - s3_start) * 1000

        total_ms = (time.perf_counter() - it_start) * 1000
        
        res = {
            "symbol": symbol,
            "decision": decision_ms,
            "fetch": fetch_ms,
            "synthesis": synth_ms,
            "total": total_ms
        }
        self.results.append(res)
        return res

def print_row(symbol, d_ms, f_ms, s_ms, t_ms, is_header=False):
    if is_header:
        print(f"{Fore.WHITE}{Style.BRIGHT}{'SYMBOL':<8} | {'DECISION':<10} | {'FETCH':<10} | {'SYNTH':<10} | {'TOTAL':<10}{Style.RESET_ALL}")
        print("-" * 60)
    else:
        # Color coding for total latency
        color = Fore.GREEN if t_ms < 5000 else (Fore.YELLOW if t_ms < 15000 else Fore.RED)
        print(f"{symbol:<8} | {d_ms:7.0f}ms | {f_ms:7.0f}ms | {s_ms:7.0f}ms | {color}{t_ms:7.0f}ms{Style.RESET_ALL}")

def print_summary(name, results):
    if not results:
        return
    totals = [r["total"] for r in results]
    decisions = [r["decision"] for r in results]
    fetches = [r["fetch"] for r in results]
    synths = [r["synthesis"] for r in results]
    
    avg = mean(totals)
    p95 = sorted(totals)[int(len(totals) * 0.95)]
    
    print("\n" + "=" * 60)
    print(f"{Fore.CYAN}{Style.BRIGHT}PERFORMANCE SUMMARY: {name}{Style.RESET_ALL}")
    print(f"  Avg Total Latency: {Fore.WHITE}{avg/1000:,.2f}s")
    print(f"  P95 Total Latency: {Fore.WHITE}{p95/1000:,.2f}s")
    print(f"  Stage Breakdown (Avg):")
    print(f"    - Decision:  {mean(decisions):,.0f}ms")
    print(f"    - Fetch:     {mean(fetches):,.0f}ms")
    print(f"    - Synthesis: {mean(synths):,.0f}ms")
    print("=" * 60 + "\n")

async def main():
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}VLI PERFORMANCE BENCHMARK SUITE - v2.1 (CORE v FLASH){Style.RESET_ALL}")
    print(f"{INFO} Target: 1 Sequential Symbol | Cache: {Fore.RED}FORCED_OFF{Style.RESET_ALL}")
    
    # ---------------------------------------------------------
    # SET A: CLOUD CORE (GEMMA 4)
    # ---------------------------------------------------------
    print(f"\n{TEST} Starting Set A: Cloud Core (Gemma 4 31B via AI Studio)...")
    bench_a = VLIBenchmark("core", "gemma-4-31b-it")
    print_row("", 0, 0, 0, 0, is_header=True)
    
    for i, symbol in enumerate(SYMBOLS):
        try:
            res = await bench_a.run_iteration(symbol)
            print_row(symbol, res["decision"], res["fetch"], res["synthesis"], res["total"])
        except Exception as e:
            print(f"{symbol:<8} | {Fore.RED}ERROR: {str(e)[:40]}...{Style.RESET_ALL}")
            
    print_summary("LOCAL GEMMA 4 (CORE)", bench_a.results)
    
    # ---------------------------------------------------------
    # SET B: CLOUD RESEARCH (GEMINI 3.1 PRO)
    # ---------------------------------------------------------
    print(f"\n{TEST} Starting Set B: Cloud Research (Gemini 3.1 Pro via AI Studio)...")
    bench_b = VLIBenchmark("reasoning", "gemini-3.1-pro")
    print_row("", 0, 0, 0, 0, is_header=True)
    
    for i, symbol in enumerate(SYMBOLS):
        try:
            res = await bench_b.run_iteration(symbol)
            print_row(symbol, res["decision"], res["fetch"], res["synthesis"], res["total"])
        except Exception as e:
            print(f"{symbol:<8} | {Fore.RED}ERROR: {str(e)[:40]}...{Style.RESET_ALL}")
            
    print_summary("CLOUD GEMINI 3 (FLASH)", bench_b.results)

if __name__ == "__main__":
    asyncio.run(main())
