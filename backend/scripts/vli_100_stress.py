
import asyncio
import os
import sys
import time
import json
import logging
from datetime import datetime
from statistics import mean, median

# Ensure backend is in path
sys.path.append(os.getcwd())

from src.tools.finance import get_stock_quote
from src.utils.vli_metrics import log_vli_metric
from src.server.app import _invoke_vli_agent

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("vli_stress_100")

# S&P 100 Tickers (Fallback Dataset)
SP100_TICKERS = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "GOOG", "META", "BRK.B", "TSLA", "UNH",
    "JNJ", "XOM", "JPM", "V", "PG", "MA", "AVGO", "HD", "CVX", "ABBV",
    "LLY", "MRK", "PFE", "PEP", "KO", "BAC", "TMO", "COST", "WMT", "DIS",
    "CSCO", "MCD", "ABT", "ADBE", "CRM", "NFLX", "CMCSA", "TXN", "VZ", "NEE",
    "PM", "NKE", "HON", "LIN", "RTX", "UPS", "BLK", "AMD", "COP", "MS",
    "LOW", "INTC", "CAT", "UNP", "IBM", "AMAT", "GE", "SBUX", "ISRG", "GS",
    "INTU", "PLD", "MDT", "DE", "SYK", "T", "QCOM", "AMGN", "TJX", "CVS",
    "NOW", "LMT", "BKNG", "C", "ELV", "AMT", "ADP", "MDLZ", "GILD", "MO",
    "ADI", "MU", "CI", "ZTS", "REGN", "LRCX", "CB", "VRTX", "BSX", "PANW",
    "FI", "SNPS", "EQIX", "SO", "DUK", "ITW", "WM", "USB", "CL", "ICE"
]

async def run_stress_test(tickers, iterations=1):
    print(f"VLI 100-SYMBOL STRESS TEST - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Symbols: {len(tickers)}")
    print("="*60)
    
    latencies = []
    successes = 0
    failures = 0
    
    for i, ticker in enumerate(tickers):
        print(f"[{i+1}/{len(tickers)}] Testing {ticker}...", end="", flush=True)
        start = time.time()
        try:
            # We use the _invoke_vli_agent to test the entire pipeline including 429 mitigation
            command = f"What is the price of {ticker}?"
            res = await _invoke_vli_agent(command)
            duration = time.time() - start
            
            # Simple pass/fail detection
            if "ERROR" in res or "fail" in res.lower() or "timeout" in res.lower() or "not supported" in res.lower():
                status = "fail"
                failures += 1
            else:
                status = "pass"
                successes += 1
                latencies.append(duration)
            
            log_vli_metric(f"stress_100_{ticker}", duration, is_stress_test=True, status=status)
            print(f" {duration:.2f}s | {status}")
            
        except Exception as e:
            duration = time.time() - start
            failures += 1
            log_vli_metric(f"stress_100_{ticker}", duration, is_stress_test=True, status="error", metadata={"error": str(e)})
            print(f" Error: {e}")
        
        # Small delay to prevent complete exhaustion if needed, 
        # though our 429 mitigation should handle it.
        await asyncio.sleep(0.5)

    print("\n" + "="*60)
    print("STRESS TEST SUMMARY")
    print(f"Success: {successes}/{len(tickers)} ({(successes/len(tickers))*100:.1f}%)")
    print(f"Failures: {failures}/{len(tickers)}")
    if latencies:
        print(f"Avg Latency: {mean(latencies):.2f}s")
        print(f"P95 Latency: {sorted(latencies)[int(len(latencies)*0.95)]:.2f}s")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_stress_test(SP100_TICKERS))
