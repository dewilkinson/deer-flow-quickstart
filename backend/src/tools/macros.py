# Agent: Research - Core macro and data synthesis tools.
# Cobalt Multiagent - High-fidelity financial analysis platform

# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from .finance import get_stock_quote, get_sharpe_ratio, get_sortino_ratio
from .smc import get_smc_analysis

from .shared_storage import RESEARCHER_CONTEXT

logger = logging.getLogger(__name__)

from .shared_storage import RESEARCHER_CONTEXT, GLOBAL_CONTEXT

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: Dict[str, Any] = {}

# 2. Shared context: Persistent, shared by Researcher sub-modules
_SHARED_RESOURCE_CONTEXT = RESEARCHER_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


# Global cache for macro data
_MACRO_CACHE: Dict[str, Any] = {
    "data": None,
    "timestamp": None
}

# Define the standard macro set
MACRO_TICKERS = {
    "DXY": "DX-Y.NYB",
    "TNX": "^TNX",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "IWM": "IWM",
    "VIX": "^VIX",
    "GLD": "GLD",
    "BTC": "BTC-USD",
    "USO": "USO"
}

TIMEFRAMES = ["15m", "1h", "4h", "1d", "1wk"]

@tool
async def fetch_market_macros() -> str:
    """
    Fetch comprehensive market macro data for key global indices and assets.
    Includes: Dollar Index (DXY), 10Y Yield (TNX), S&P 500 (SPY), Nasdaq (QQQ), 
    Russell 2000 (IWM), Volatility (VIX), Gold (GLD), Bitcoin (BTC), and Oil (USO).
    
    Performs full SMC analysis across 15m, 1h, 4h, 1d, and 1w timeframes for all tickers.
    
    NOTE: This tool features a 15-minute cooldown cache to prevent excessive API calls.
    """
    global _MACRO_CACHE
    
    # Cache Check
    if _MACRO_CACHE["timestamp"] and _MACRO_CACHE["data"]:
        elapsed = datetime.now() - _MACRO_CACHE["timestamp"]
        if elapsed < timedelta(minutes=15):
            logger.info(f"Using cached macro data (Age: {elapsed.total_seconds():.0f}s)")
            return f"**[CACHED]** - Last refresh: {_MACRO_CACHE['timestamp'].strftime('%H:%M:%S')}\n\n{_MACRO_CACHE['data']}"

    logger.info("Starting global macro fetch sequence (Cache miss/expire)...")
    
    async def process_ticker(label: str, yahoo_ticker: str):
        logger.info(f"Processing macro: {label} ({yahoo_ticker})")
        
        # 1. Fetch current quote
        quote = await get_stock_quote.ainvoke({"ticker": yahoo_ticker, "period": "5d", "interval": "1d"})
        
        # 2. Fetch SMC for all timeframes in parallel
        smc_tasks = [
            get_smc_analysis.ainvoke({"ticker": yahoo_ticker, "period": "60d", "interval": tf}) 
            for tf in TIMEFRAMES
        ]
        smc_results = await asyncio.gather(*smc_tasks)
        
        smc_summary = ""
        for tf, res in zip(TIMEFRAMES, smc_results):
            tf_data = str(res)
            trend = "Bullish" if "Bullish" in tf_data else "Bearish" if "Bearish" in tf_data else "Neutral"
            smc_summary += f"- **{tf}**: {trend}\n"
        
        section = f"""
## {label} ({yahoo_ticker})
{quote if isinstance(quote, str) else "Data unavailable"}

### Multi-Timeframe SMC Trend
{smc_summary}
---
"""
        return section

    tasks = [process_ticker(label, ticker) for label, ticker in MACRO_TICKERS.items()]
    results = await asyncio.gather(*tasks)
    
    final_report = "# 🌐 Global Market Macro Report\n\n"
    report_content = "".join(results)
    final_report += report_content
    
    # Update cache ONLY if no major errors occurred in the report
    if "[ERROR]" not in report_content:
        _MACRO_CACHE["data"] = final_report.strip()
        _MACRO_CACHE["timestamp"] = datetime.now()
        logger.info("Macro report cached successfully.")
    else:
        logger.warning("Macro report contains errors. Skipping caching to allow immediate retry.")
    
    return final_report.strip()
