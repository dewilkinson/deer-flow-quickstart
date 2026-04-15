# Agent: Research - Core macro and data synthesis tools.
# Cobalt Multiagent - High-fidelity financial analysis platform

# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import asyncio
import logging
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from src.services.macro_registry import macro_registry

from src.config.vli import get_vli_path
from .finance import _extract_ticker_data, _fetch_batch_history, get_symbol_history_data
from .shared_storage import ANALYST_CONTEXT, GLOBAL_CONTEXT

NY_TZ = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)

# 1. Private to the Agent Code Itself
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context
_SHARED_RESOURCE_CONTEXT = ANALYST_CONTEXT

# 3. Global context
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT


# Global cache for macro data
_MACRO_CACHE: dict[str, Any] = {"data": None, "timestamp": None}


# Registry-backed Macro Symbol Set
def get_macro_tickers():
    return macro_registry.get_macros()


# The following are maintained for legacy compatibility but now proxy to the registry
MACRO_TICKERS = get_macro_tickers()

MACRO_NAMES = {
    "VIX": "CBOE Volatility Index",
    "DXY": "US Dollar Index",
    "TNX": "10-Year Treasury Yield",
    "SPY": "S&P 500 Trust ETF",
    "QQQ": "Nasdaq 100 ETF",
    "IWM": "Russell 2000 ETF",
    "SI": "Silver Futures",
    "BTC": "Bitcoin (USD)",
    "USO": "United States Oil Fund",
    "WTI": "WTI Crude Oil",
}

TIMEFRAMES = ["1h", "1d"]


@tool
async def fetch_market_macros() -> str:
    """
    Fetch comprehensive market macro data for key global indices and assets.
    Utilizes the Ground Truth Macro Watchlist state for consistency with the dashboard.
    Provides price, trend, volume, and regime analysis.
    """
    import json
    import os
    
    # 1. Try to load Ground Truth from the Macro Watchlist Bucket
    state_path = get_vli_path("01_Transit/Buckets/MACRO_WATCHLIST_state.json")
    bucket_data = {}
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
                bucket_data = state.get("data", {})
                logger.info(f"[MACRO_TOOL] Ingested ground truth for {len(bucket_data)} symbols from {state.get('last_updated')}")
        except Exception as e:
            logger.error(f"Failed to read Macro Watchlist state: {e}")

    # 2. Fetch live/structured data as fallback or for missing symbols
    data = await get_macro_data()
    if not data and not bucket_data:
        return "Error: Unable to synthesize macro market data at this time."

    report = "## [GROUND_TRUTH]: Macro Market Environment Report\n"
    report += f"Source: VLI Persistent Bucket Engine | Sync Time: {datetime.now().strftime('%H:%M:%S')}\n\n"

    # Merge logic: Prioritize Bucket Data (includes Regime, Volume, and high-fidelity price changes)
    all_labels = set(bucket_data.keys()) | {item["label"] for item in data}
    
    for label in sorted(list(all_labels)):
        name = MACRO_NAMES.get(label, "Index")
        
        # Prefer bucket data as it contains finalized Regimes from the specialized tool
        if label in bucket_data:
            item = bucket_data[label]
            price = item.get("Price", 0.0)
            change = item.get("Change %", 0.0)
            volume = item.get("Volume", "N/A")
            regime = item.get("Regime", "UNKNOWN")
            sortino = item.get("Sortino", 0.0)
            
            # Format report for the specialist
            report += f"### {label} ({name})\n"
            report += f"- **Current Price**: ${price:,.2f} ({change:+.2f}%)\n"
            report += f"- **Regime Status**: {regime}\n"
            
            # Add Sortino (Risk-Adjusted Consistency)
            if sortino:
                report += f"- **Sortino Ratio (Day Trading)**: {sortino:.2f} (Consistency Score)\n"
            
            # Add Volume Profile Node Analysis
            vp = item.get("Volume_Profile", {})
            if isinstance(vp, dict) and "metadata" in vp:
                meta = vp["metadata"]
                report += f"- **Volume Profile Nodes**: POC at ${meta.get('poc')}, Value Area [${meta.get('val')} - ${meta.get('vah')}]\n"
            
            # SMC / Trend
            smc = item.get("SMC_Raw", "")
            if smc:
                # Truncate raw SMC for report brevity if it's too long
                smc_summary = str(smc)[:200] + "..." if len(str(smc)) > 200 else str(smc)
                report += f"- **SMC/Trend Context**: {smc_summary}\n"
            
            report += f"- **Volume Activity**: {volume}\n\n"

        else:
            # Fallback to get_macro_data results if not in bucket
            item = next((i for i in data if i["label"] == label), None)
            if item:
                report += f"### {label} ({name})\n"
                report += f"- **Price**: ${item['price']:,.2f}\n"
                report += f"- **Change**: {item['change']:+.2f}%\n"
                report += "- **Status**: Retaining session parity...\n\n"

    return report



_LOOKBACK = 10
_INTERVAL = "1h"
_LOOKBACK = 10
_INTERVAL = "1h"


async def get_macro_data() -> list[dict[str, Any]]:
    """
    Structured version of market macros for API consumption.
    Refactored for speed:
    1. Bulk fetch quotes for all tickers.
    2. Parallelize SMC/Sortino tasks (throttled by the global finance lock).
    """
    logger.info(f"Fetching structured macro data (LB={_LOOKBACK}, INT={_INTERVAL})...")

    # Fetch from dynamic registry
    current_macros = macro_registry.get_macros()
    tickers = list(current_macros.values())
    labels = list(current_macros.keys())

    # 1. Bulk Fetch Quotes (15m for speed)
    history_report = await get_symbol_history_data.ainvoke({"symbols": tickers, "period": "1d", "interval": "15m"})

    # 2. Bulk Fetch Sparklines (last 5 days)
    sparkline_data = await asyncio.to_thread(_fetch_batch_history, tickers, "5d", _INTERVAL)

    # Parse prices from bulk report
    prices = {}
    for line in history_report.split("###"):
        if not line.strip():
            continue
        try:
            name_part = line.split("\n")[0].strip()
            close_match = re.search(r"Close\*\*:\s*([\d\.,]+)", line)
            if close_match:
                prices[name_part] = float(close_match.group(1).replace(",", ""))
        except Exception as e:
            logger.error(f"Error parsing price for part: {e}")

    async def process_one(label: str, yahoo_ticker: str):
        try:
            # Extract Sparkline and calculate % Change
            sparkline = []
            change_pct = 0.0
            try:
                ticker_spark_df = _extract_ticker_data(sparkline_data, yahoo_ticker)
                if not ticker_spark_df.empty:
                    # Calculate % change from start of period
                    start_price = float(ticker_spark_df.iloc[0]["Close"])
                    current_price = float(ticker_spark_df.iloc[-1]["Close"])
                    if start_price > 0:
                        change_pct = ((current_price - start_price) / start_price) * 100

                    # Take last _LOOKBACK non-null values for the UI charts
                    last_n = ticker_spark_df.tail(_LOOKBACK)
                    for _, row in last_n.iterrows():
                        ts = row.name
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=ZoneInfo("UTC"))

                        sparkline.append({"v": float(row["Close"]), "t": ts.astimezone(NY_TZ).strftime(" %m/%d  %I:%M %p").lower()})
            except Exception as e:
                logger.error(f"Sparkline error for {yahoo_ticker}: {e}")

            return {
                "label": label,
                "name": MACRO_NAMES.get(label, ""),
                "ticker": yahoo_ticker,
                "price": prices.get(yahoo_ticker, 0.0) or prices.get(yahoo_ticker.upper(), 0.0),
                "change": change_pct,
                "sortino": 0.0,
                "trends": {},
                "sparkline": sparkline,
            }
        except Exception as e:
            logger.error(f"Error {label}: {e}")
            return {"label": label, "name": MACRO_NAMES.get(label, ""), "ticker": yahoo_ticker, "price": 0.0, "change": 0.0, "sortino": 0.0, "trends": {}, "sparkline": []}

    # 3. Parallelize processing (Now extremely fast since no sub-tool calls are made)
    tasks = [process_one(l, t) for l, t in MACRO_TICKERS.items()]
    results = await asyncio.gather(*tasks)

    now = datetime.now()
    _MACRO_CACHE["data"] = results
    _MACRO_CACHE["timestamp"] = now
    return results
