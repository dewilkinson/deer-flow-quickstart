# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Agent: Scout - Core financial primitives and data retrieval.
# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import asyncio
import logging
import threading
import time
import datetime
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import numpy as np
import yfinance

# Use curl_cffi for industrial-strength browser spoofing
from curl_cffi.requests import Session
from langchain_core.tools import tool
from src.services.datastore import DatastoreManager

logger = logging.getLogger(__name__)

from src.tools.shared_storage import GLOBAL_CONTEXT, SCOUT_CONTEXT, history_cache

from .scraper import fetch_finviz_quotes
from .screenshot import snapper
from src.utils.temporal import get_effective_now

# 1. Private context
_NODE_RESOURCE_CONTEXT: dict[str, Any] = {}

# 2. Shared context
_SHARED_RESOURCE_CONTEXT = SCOUT_CONTEXT

# 3. Global context: Shared across all agent types
_GLOBAL_RESOURCE_CONTEXT = GLOBAL_CONTEXT

# 4. Specialized Analysis Cache (Isolated from Scout)
_ANALYSIS_CACHE: dict[str, Any] = {}

# Global semaphore to prevent slamming Yahoo Finance API
# We limit to 3 concurrent network requests to prevent rate limiting and head-of-line blocking.
_YF_SEMAPHORE: asyncio.Semaphore | None = None


def _get_yf_semaphore() -> asyncio.Semaphore:
    """Lazy initialization of the semaphore in the correct event loop."""
    global _YF_SEMAPHORE
    if _YF_SEMAPHORE is None:
        _YF_SEMAPHORE = asyncio.Semaphore(3)
    return _YF_SEMAPHORE


# Thread-local storage for sessions to avoid pickling/multiprocessing issues
_thread_local = threading.local()


def _get_session():
    """Retrieve a fresh curl_cffi session to prevent TCP connection stalling on sequential API calls."""
    session = Session(impersonate="chrome120", timeout=30.0)
    session.headers.update({"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9", "Referer": "https://finance.yahoo.com/"})
    return session


# Datastore registration is moved to the bottom of the file to prevent circular imports


def _normalize_ticker(ticker: str) -> str:
    """Consistently maps common tickers to their Yahoo Finance equivalents."""
    # Strip any existing index markers to prevent double-normalization (^VIX -> ^^VIX)
    t = ticker.upper().strip().lstrip("^")
    
    if t == "VIX":
        return "^VIX"
    if t == "SPX":
        return "^GSPC"
    if t == "NDX":
        return "^NDX"
    if t == "DXY":
        return "DX-Y.NYB"
    if t == "TNX":
        return "^TNX"
    if t == "TYX":
        return "^TYX"
    if t == "FVX":
        return "^FVX"
    if t == "BTC" or t == "BTCUSDT":
        return "BTC-USD"
    if t == "ETH" or t == "ETHUSDT":
        return "ETH-USD"
    if t.endswith("USDT"):
        return t.replace("USDT", "-USD")
    if t == "GC" or t == "GOLD":
        return "GC=F"
    if t == "SI" or t == "SILVER":
        return "SI=F"
    if t == "WTI" or t == "CRUDE" or t == "OIL":
        return "CL=F"
    if t == "EURUSD" or t == "EUR/USD":
        return "EURUSD=X"
    if t == "GBPUSD" or t == "GBP/USD":
        return "GBPUSD=X"

    # Handle S&P 100 / Common Discrepancies (Dots to Hyphens)
    # e.g., BRK.B -> BRK-B, BF.B -> BF-B
    # EXCLUSION: DX-Y.NYB requires the dot to be preserved
    if "." in t and t != "DX-Y.NYB":
        return t.replace(".", "-")

    return t


def _bucket_sparkline_data(df: pd.DataFrame, ref_time: datetime, current_price: float, num_points: int = 20, span_minutes: int = 390) -> list[float | None]:
    """
    High-Fidelity Resampling: Spans span_minutes ending at ref_time.
    Defaults to 20 points over 390 minutes (9:30 AM - 4:00 PM trading session).
    """
    if df.empty:
        return [round(current_price, 4)] * num_points

    col = "Close" if "Close" in df.columns else "close"
    
    # Check for duplicated columns safely
    target_data = df[col]
    if isinstance(target_data, pd.DataFrame):
        target_data = target_data.iloc[:, 0]
        
    # Crucial Fix: Drop NaN values that leak from multi-ticker batch unions
    target_data = target_data.dropna()
    
    # Ensure index is correctly unified to Naive EDT
    try:
        if getattr(df.index, 'tz', None) is not None:
            df.index = df.index.tz_convert('America/New_York').tz_localize(None)
        else:
            df.index = pd.to_datetime(df.index)
    except Exception as e:
        pass
    
    temp_series = target_data.sort_index()
    last_data_time = temp_series.index.max()
    
    # Calculate the exact 20-point grid spanning the window
    start_time = ref_time - timedelta(minutes=span_minutes)
    target_index = pd.date_range(start=start_time, end=ref_time, periods=num_points).round('s')
    
    values = []
    for i, target_time in enumerate(target_index):
        # [ROBUST_LOOKUP] Find the last price available at or before the target time
        tt = target_time
        if getattr(temp_series.index, 'tz', None) is not None:
            tt = target_time.tz_localize('America/New_York').tz_convert(temp_series.index.tz)
            
        try:
            val = temp_series.asof(tt)
        except Exception as e:
            val = None
        
        if pd.isna(val):
            values.append(None)
            continue
            
        final_val = val if i < len(target_index) - 1 else current_price
        values.append(round(float(final_val), 4))
            
    # [STABILITY] Forward fill None values to maintain trend flow
    for i in range(len(values)):
        if values[i] is None:
            if i == 0:
                # Find first valid future value
                future_vals = [v for v in values if v is not None]
                values[i] = future_vals[0] if future_vals else round(current_price, 4)
            else:
                values[i] = values[i-1] # Forward fill
                
    return values
        
    return values


def _fetch_batch_history(tickers: list[str], period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """
    Centralized batched fetcher for Yahoo Finance data.
    Ensures all requests are batched where possible.
    Note: Throttling is now handled by the caller via the _YF_SEMAPHORE.
    """
    logger.info(f"Executing batched fetch for {tickers} (p={period}, i={interval})")
    
    # [UNIVERSAL_TEMPORAL_INSTRUMENTATION]
    # Check if we are in Replay mode and trigger the sliding window fetcher
    from src.utils.temporal import get_effective_now
    ref_time = get_effective_now()
    now = datetime.now()
    
    # If ref_time is more than 5 seconds away from 'now', we assume Replay Mode
    if abs((now - ref_time).total_seconds()) > 5:
        logger.info(f"VLI_REPLAY: Universal delegation for {tickers} (Target Origin: {ref_time})")
        return _fetch_replay_history(tickers, period, interval, end_date=ref_time)

    mapped_tickers = [_normalize_ticker(t) for t in tickers]

    logger.debug(f"[WEB REQUEST] Yahoo Finance fetching {len(mapped_tickers)} tickers: {mapped_tickers}")
    start_time = time.time()
    try:
        data = yfinance.download(
            tickers=mapped_tickers,
            period=period,
            interval=interval,
            group_by="ticker",
            session=_get_session(),
            progress=False,
            threads=False,  # Maintain throttle integrity
            timeout=10.0,
            auto_adjust=False, # [SPLIT_AWARENESS] Return both nominal and adjusted
            prepost=True,      # [EXTENDED_HOURS] Support pre/post market trading
        )
        duration_ms = (time.time() - start_time) * 1000

        if data is not None and not data.empty:
            logger.debug(f"[WEB RESPONSE] Yahoo Finance fetch successful in {duration_ms:.2f}ms for {mapped_tickers}")
        else:
            logger.warning(f"[WEB RESPONSE] Yahoo Finance returned empty data in {duration_ms:.2f}ms for {mapped_tickers}")
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[ERROR] Yahoo Finance fetch failed after {duration_ms:.2f}ms for {mapped_tickers}: {e}", exc_info=True)
        raise

    # Hard delay to prevent rate limiting
    time.sleep(1.0)
    return data


def _fetch_replay_history(tickers: list[str], period: str = "5d", interval: str = "1d", end_date: datetime = None) -> pd.DataFrame:
    """
    Sub-fetcher for Replay Engine which forces a sliding window relative to a historical origin.
    Automatically downsamples intervals if the origin is too old (e.g. 1m data limited to last 30 days).
    """
    # 1. Adaptive Downsampling
    now = datetime.now()
    if end_date and (now - end_date).days > 29:
        if interval in ["1m", "2m", "5m"]:
            logger.info(f"VLI_REPLAY: Auto-downsampling interval from {interval} to 1d (Origin > 30 days old)")
            interval = "1d"
        elif interval in ["15m", "30m", "60m", "1h"]:
            logger.info(f"VLI_REPLAY: Auto-downsampling interval from {interval} to 1d (Origin > 730 days limit for 1h)")
            if (now - end_date).days > 720:
                interval = "1d"

    logger.info(f"VLI_REPLAY: Fetching {tickers} (p={period}, i={interval}) ending at {end_date}")
    mapped_tickers = [_normalize_ticker(t) for t in tickers]
    
    # Calculate start_date if period is given (approximate)
    # yfinance handles 'period' internally if 'end' is provided, but 'start' is safer for specific windows
    # Actually yfinance 0.2.x handles start/end well.
    
    start_time = time.time()
    try:
        data = yfinance.download(
            tickers=mapped_tickers,
            period=period,
            end=end_date,
            interval=interval,
            group_by="ticker",
            session=_get_session(),
            progress=False,
            threads=False,
            timeout=10.0,
            auto_adjust=False, # [SPLIT_AWARENESS] Maintain nominal scale for reporting
        )
        duration_ms = (time.time() - start_time) * 1000
        logger.debug(f"VLI_REPLAY: fetch successful in {duration_ms:.2f}ms")
        return data
    except Exception as e:
        logger.error(f"VLI_REPLAY: fetch failed: {e}")
        raise


def _extract_ticker_data(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Helper to extract a single ticker's dataframe from a multi-index yf.download result.
    Will automatically try normalized ticker names if the original key is not present.
    """
    ticker_upper = ticker.upper()
    norm_ticker = _normalize_ticker(ticker)

    print(f"DEBUG _extract_ticker_data: ticker={ticker}, ticker_upper={ticker_upper}, is_multi={isinstance(df.columns, pd.MultiIndex)}, df.columns={type(df.columns)}")

    if isinstance(df.columns, pd.MultiIndex):
        # 1. Try original ticker
        if ticker_upper in df.columns.levels[0]:
            res = df[ticker_upper].dropna(how="all").copy()
            if isinstance(res.columns, pd.MultiIndex): res.columns = [c[0] for c in res.columns]
            return res
        if len(df.columns.levels) > 1 and ticker_upper in df.columns.levels[1]:
            res = df.xs(ticker_upper, level=1, axis=1).dropna(how="all").copy()
            if isinstance(res.columns, pd.MultiIndex): res.columns = [c[0] for c in res.columns]
            return res

        # 2. Try normalized ticker (VIX -> ^VIX)
        if norm_ticker in df.columns.levels[0]:
            res = df[norm_ticker].dropna(how="all").copy()
            if isinstance(res.columns, pd.MultiIndex): res.columns = [c[0] for c in res.columns]
            return res
        if len(df.columns.levels) > 1 and norm_ticker in df.columns.levels[1]:
            res = df.xs(norm_ticker, level=1, axis=1).dropna(how="all").copy()
            if isinstance(res.columns, pd.MultiIndex): res.columns = [c[0] for c in res.columns]
            return res

        # 3. Fallback to direct access if columns levels are flattened
        try:
            return df[ticker_upper].dropna(how="all").copy()
        except:
            pass
        try:
            return df[norm_ticker].dropna(how="all").copy()
        except:
            pass
            
        # [CROSS_CONTAMINATION_GUARD] Stop matching here if MultiIndex doesn't contain ticker at all
        return pd.DataFrame()

    # Flat Index Case
    return df.dropna(how="all").copy()


def _get_ttl_seconds(interval: str) -> int:
    """Helper to determine cache TTL in seconds based on interval granularity."""
    i = interval.lower()
    if i in ["1m"]:
        return 60
    if i in ["2m"]:
        return 120
    if i in ["5m"]:
        return 300
    if i in ["15m"]:
        return 900
    if i in ["30m"]:
        return 1800
    if i in ["1h", "60m"]:
        return 3600
    if i in ["2h", "4h"]:
        return 3600 * 2
    if i in ["1d", "1wk", "1mo"]:
        return 86400  # EOD cache for macro bounds
    return 300  # default 5m


def _fetch_stock_history(ticker: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """
    Standard single-ticker fetcher. Automatically flattens MultiIndex for the requested ticker.
    Used by all analysis nodes (Analyst, SMC, EMA, etc.). Heavily cached to prevent LangGraph sequential redundant fetching.
    """
    norm_ticker = _normalize_ticker(ticker)
    from src.utils.temporal import get_cache_segment_suffix
    suffix = get_cache_segment_suffix()
    cache_key = f"{norm_ticker}{suffix}_{period}_{interval}"

    df_cache = DatastoreManager.get_df_cache()

    if cache_key in df_cache:
        entry = df_cache[cache_key]
        if "last_updated" in entry and "df" in entry:
            age_sec = (datetime.now() - entry["last_updated"]).total_seconds()
            ttl = _get_ttl_seconds(interval)
            if age_sec < ttl:
                logger.info(f"[DF_CACHE HIT] Reusing {norm_ticker} data (Age: {age_sec:.1f}s / TTL: {ttl}s)")
                return entry["df"].copy()
            else:
                logger.info(f"[DF_CACHE EXPIRED] Ticker {norm_ticker} data is {age_sec:.1f}s old (TTL: {ttl}s)")

    data = _fetch_batch_history([ticker], period, interval)
    df = _extract_ticker_data(data, ticker)

    df_cache[cache_key] = {"df": df.copy(), "last_updated": datetime.now()}
    return df.copy()


def _fetch_stock_history_vli(ticker: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """Consolidated history fetcher with universal Replay and Cache support."""
    return _fetch_stock_history(ticker, period, interval)


@tool
async def get_symbol_history_data(symbols: list[str], period: str = "1d", interval: str = "1h", verbosity: int = 1, is_test_mode: bool = False) -> str:
    """
    Scout Primitive: Retrieve stock history for multiple symbols in a single batched request.
    Verbosity levels: 1 (Report only), 2 (Include fetch traces).
    """
    from datetime import datetime

    from src.config.loader import get_int_env

    expiry_minutes = get_int_env("CACHE_EXPIRY_MINUTES", 15)
    DatastoreManager.ensure_worker_started()

    logger.info(f"Scout fetching history for {symbols}")

    # Datastore cache bridge
    history_cache = DatastoreManager.get_history_cache()
    # Tracker removed

    now = datetime.now()
    results = []
    missing_symbols = []
    symbols_upper = [s.upper() for s in symbols]

    for sym in symbols:
        sym = sym.upper()
        # No heat tracking for Scout

        # Refactor Phase 2: Use DatastoreManager.get_artifact
        cached_entry = DatastoreManager.get_artifact(sym, "history", interval)
        
        is_stale = True
        if cached_entry and "updated_at" in cached_entry:
            age_min = (now - cached_entry["updated_at"]).total_seconds() / 60.0
            if age_min <= expiry_minutes:
                is_stale = False

        if not is_stale:
            logger.info(f"[CACHE_READ] Using warm lazy cache for {sym}")
            data_val = cached_entry["data"]
            if isinstance(data_val, dict) and "data" in data_val:
                results.append(data_val["data"])
            else:
                results.append(data_val)
        else:
            if cached_entry:
                logger.info(f"[CACHE_EVICT] Data for {sym} is stale. Fetching fresh data.")
            missing_symbols.append(sym)

    if missing_symbols:
        # Diagnostic check for mocks
        mocks = [s for s in missing_symbols if s.startswith(("HIGH_", "MOD_", "INACT_"))]
        others = [s for s in missing_symbols if s not in mocks]

        for m in mocks:
            results.append(f"### {m}\n- [MOCK DATA]: {m} retrieved from diagnostic seed.")

        if others:
            try:
                # Use semaphore for throttling
                async with _get_yf_semaphore():
                    # [REPLAY_INSTRUMENTATION] Check for temporal shift
                    ref_time = get_effective_now()
                    is_replay = (ref_time.date() < datetime.now().date())
                    
                    if is_replay:
                        full_df = await asyncio.wait_for(asyncio.to_thread(_fetch_replay_history, others, period, interval, end_date=ref_time), timeout=15.0)
                    else:
                        full_df = await asyncio.wait_for(asyncio.to_thread(_fetch_batch_history, others, period, interval), timeout=15.0)

                for sym in others:
                    ticker_df = _extract_ticker_data(full_df, sym)
                    if ticker_df.empty:
                        # Fallback to Finviz
                        try:
                            f_data = await fetch_finviz_quotes([sym])
                            if sym.upper() in f_data:
                                q = f_data[sym.upper()]
                                data_str = f"### {sym}\n- **Price**: {q['price']:.2f}\n- **Volume**: {q['volume']:,}\n- **Source**: Finviz (Fallback)"
                                results.append(data_str)
                                # Refactor Phase 2/3: Store with current price for drift check
                                DatastoreManager.store_artifact(sym, "history", interval, data_str, price=float(q["price"]))
                                continue
                        except:
                            pass
                        results.append(f"### {sym}\n- [ERROR]: Data retrieval failed.")
                        continue

                    last_row = ticker_df.iloc[-1]
                    # Ensure full OHLCV and Symbol are cached together in shared memory
                    raw_ohlcv = {
                        "Symbol": sym,
                        "Open": float(last_row.get("Open", 0)),
                        "High": float(last_row.get("High", 0)),
                        "Low": float(last_row.get("Low", 0)),
                        "Close": float(last_row.get("Close", 0)),
                        "Volume": int(last_row.get("Volume", 0)),
                    }
                    data_str = f"### {sym}\n- **Period**: {period} | **Interval**: {interval}\n- **Open**: {raw_ohlcv['Open']:.2f}\n- **High**: {raw_ohlcv['High']:.2f}\n- **Low**: {raw_ohlcv['Low']:.2f}\n- **Close**: {raw_ohlcv['Close']:.2f}\n- **Volume**: {raw_ohlcv['Volume']:,}\n"

                    # Refactor Phase 2/3: Store with current price for drift check
                    current_price = raw_ohlcv["Close"]
                    DatastoreManager.store_artifact(sym, "history", interval, {"data": data_str, "raw": raw_ohlcv}, price=current_price)
                    results.append(data_str)
            except TimeoutError:
                logger.error(f"Timeout: Fetch for {others} timed out.")
                results.append(f"### {others}\n- [ERROR]: Timeout during data retrieval.")
            except Exception as e:
                logger.error(f"Fetch error: {e}")
                results.append(f"### {others}\n- [ERROR]: {str(e)}")

    report = f"# Stock History Report\nGenerated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    report += "\n".join([str(r) for r in results])
    return report.strip()


@tool
async def simulate_cache_volatility(num_high: int = 10, num_moderate: int = 30, num_inactive: int = 10) -> str:
    """
    Scout Primitive (Diagnostic): Artificially populates the global cache with mock tickers of varying usage 'heat' to test eager/lazy architecture.
    """
    from datetime import datetime, timedelta

    ticker_metadata = _GLOBAL_RESOURCE_CONTEXT.setdefault("ticker_metadata", {})
    history_cache = DatastoreManager.get_history_cache()
    cached_tickers_set = _GLOBAL_RESOURCE_CONTEXT.setdefault("cached_tickers", set())

    now = datetime.now()
    stale_time = now - timedelta(seconds=10)  # Immediately push past 5s boundary

    # 10 High Activity
    for i in range(num_high):
        sym = f"HIGH_{i}"
        ticker_metadata[sym] = {"heat": 100}
        from src.services.heat_manager import HeatManager
        # Force high heat in new Manager
        HeatManager.increment_heat(sym, 100.0)
        DatastoreManager.store_artifact(sym, "history", "1h", f"### {sym}\nMock high heat", price=100.0)
        cached_tickers_set.add(sym)

    # 30 Moderate Activity
    for i in range(num_moderate):
        sym = f"MOD_{i}"
        ticker_metadata[sym] = {"heat": 10}
        HeatManager.increment_heat(sym, 10.0)
        DatastoreManager.store_artifact(sym, "history", "1h", f"### {sym}\nMock mod heat", price=100.0)
        cached_tickers_set.add(sym)

    # 10 Inactive
    for i in range(num_inactive):
        sym = f"INACT_{i}"
        ticker_metadata[sym] = {"heat": 1}
        HeatManager.increment_heat(sym, 1.0)
        DatastoreManager.store_artifact(sym, "history", "1h", f"### {sym}\nMock inactive", price=100.0)
        cached_tickers_set.add(sym)

    # Simulate random clicks to reach final distribution
    import random

    mock_tickers = [f"HIGH_{i}" for i in range(num_high)] + [f"MOD_{i}" for i in range(num_moderate)] + [f"INACT_{i}" for i in range(num_inactive)]

    # We want HIGH tickers to have lots of hits (bar visualization)
    for sym in mock_tickers:
        meta = ticker_metadata[sym]
        if sym.startswith("HIGH_"):
            meta["heat"] = random.randint(25, 45)
        elif sym.startswith("MOD_"):
            meta["heat"] = random.randint(8, 18)
        else:
            meta["heat"] = random.randint(1, 3)

    logger.info(f"[CACHE_DIAGNOSTIC] Generated distribution: {num_high} high, {num_moderate} moderate, {num_inactive} inactive.")
    return "Successfully populated 50 mock stocks with distribution 10/30/10. Visual Heat Map is now available."


@tool
async def get_cache_heat_map() -> str:
    """
    System Admin Tool: Generates a high-fidelity visual representation of the current cache 'heat' distribution.
    Shows frequency counters using bar visualizations and color-coded health states.
    """
    ticker_metadata = _GLOBAL_RESOURCE_CONTEXT.get("ticker_metadata", {})
    if not ticker_metadata:
        return "Cache is currently empty."

    sorted_tickers = sorted(ticker_metadata.keys(), key=lambda s: ticker_metadata[s].get("heat", 0), reverse=True)

    lines = ["# VLI Hybrid Cache Heat Map", ""]
    lines.append("| Ticker | Heat Level | Activity Bar | Status |")
    lines.append("| :--- | :--- | :--- | :--- |")

    for sym in sorted_tickers:
        heat = ticker_metadata[sym].get("heat", 0)

        # Determine Color/Category
        if heat >= 25:
            status = "🟣 **Top 5**" if sorted_tickers.index(sym) < 5 else "🟢 **Top 10**"
            bar_char = "█"
        elif heat >= 8:
            status = "🟠 **Active**"
            bar_char = "▓"
        elif heat >= 4:
            status = "🟡 **Lazy**"
            bar_char = "▒"
        else:
            status = "🔴 **Evictable**"
            bar_char = "░"

        bar = bar_char * min(heat, 20)  # Cap bar length for UI
        if heat > 20:
            bar += "+"

        lines.append(f"| {sym} | {heat} | `{bar}` | {status} |")

    return "\n".join([str(l) for l in lines])


@tool
async def vli_cache_tick(iteration: int) -> str:
    """
    VLI System Diagnostic (Heartbeat): Executes a single iterative tick of the VLI autonomic cache simulation.
    Handles symbol arrival, heat decay, and trace generation.
    """
    import random

    # Persistent state for the diagnostic run
    diag_state = GLOBAL_CONTEXT.setdefault("vli_cache_diag", {"cache": {}, "history": []})
    cache = diag_state["cache"]
    traces = [f"### VLI Cache Heartbeat (Tick {iteration}/5)"]

    # 1. Decay Phase (Execute every tick)
    evicted = []
    for sym, data in list(cache.items()):
        data["heat"] -= 1
        if data["heat"] <= 0:
            evicted.append(sym)
            del cache[sym]
        else:
            traces.append(f"[CACHE_TRACE] Symbol {sym} heat decremented to {data['heat']} via decay.")

    for sym in evicted:
        traces.append(f"[CACHE_TRACE] Symbol {sym} evicted from cache due to TTL decay (Heat reached 0).")

    # 2. Arrival Phase (One new random symbol per tick)
    # 50 mocked 3-letter symbols (Simple subset: AAA-ZZZ)
    ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    new_sym = "".join(random.choices(ALPHABET, k=3))

    traces.append(f"[CACHE_TRACE] New symbol presentation: {new_sym} entering VLI pipeline.")

    if new_sym in cache:
        cache[new_sym]["heat"] += 1
        traces.append(f"[CACHE_TRACE] Symbol {new_sym} updated in contextual cache (Heat: {cache[new_sym]['heat']}).")
    else:
        cache[new_sym] = {"price": f"{random.uniform(50, 500):.2f}", "volume": f"{random.randint(1000, 100000)}", "heat": 1}
        traces.append(f"[CACHE_TRACE] Symbol {new_sym} added to contextual cache (Heat: 1).")

    # 3. Visualization Phase (Generate Dynamic Table JSON)
    rows = []
    for sym, data in cache.items():
        rows.append([sym, data["price"], data["volume"], {"type": "indicator", "value": data["heat"]}])

    table_json = {"type": "table", "id": f"vli_diag_tick_{iteration}", "headers": ["SYMBOL", "PRICE", "VOLUME", "HEAT"], "rows": rows}

    import json

    report = "\n".join([str(t) for t in traces]) + "\n\n```json\n" + json.dumps(table_json) + "\n```"
    return report


@tool
async def clear_vli_diagnostic() -> str:
    """
    VLI System Administrative Tool: Resets the autonomic cache simulation.
    Clears all persistent symbols, heat data, and trace history.
    """
    GLOBAL_CONTEXT["vli_cache_diag"] = {"cache": {}, "history": []}
    logger.info("[VLI_ADMIN] Cache simulation state has been reset.")
    return "VLI Cache Simulation state has been successfully cleared. Ready for fresh diagnostic run."


@tool
async def get_stock_quote(ticker: str, period: str = "1d", interval: str = "1m", use_fast_path: bool = True, use_finviz_fallback: bool = False, force_refresh: bool = False) -> dict[str, Any] | str:
    """Retrieve realtime or delayed stock quote for a specific ticker symbol. Fast-fetch skips full history parsing where possible.
    If 'use_finviz_fallback' is True, it strictly bypasses Yahoo Finance and fetches directly via the Finviz scraper module.
    If 'force_refresh' is True, it invalidates any existing cache for this symbol before fetching."""

    DatastoreManager.ensure_worker_started()
    norm_ticker = _normalize_ticker(ticker)

    logger.info(f"[DIAGNOSTIC] get_stock_quote called for {ticker} | force_refresh={force_refresh} | use_fast_path={use_fast_path}")

    if force_refresh:
        logger.info(f"VLI_SYSTEM: Force refresh requested for {ticker}. Invalidating cache.")
        DatastoreManager.invalidate_cache(norm_ticker)

    if use_finviz_fallback:
        logger.info(f"VLI_SYSTEM: User explicitly requested Finviz fallback for {ticker}.")
        try:
            fin_quotes = await fetch_finviz_quotes([norm_ticker])
            if norm_ticker.upper() in [k.upper() for k in fin_quotes.keys()]:
                quote = fin_quotes[norm_ticker.upper()]
                return {"symbol": norm_ticker, "price": quote["price"], "volume": quote["volume"], "source": f"Finviz {quote['source']} (Explicit Override)", "note": "[VLI_SYSTEM] Successfully extracted via Finviz scraper as requested."}
        except Exception as e:
            logger.error(f"Explicit Finviz fallback failed: {e}")
            return f"[ERROR]: Requested Finviz fallback failed to extract data: {e}"

    try:
        # 1. Warm Cache Phase: Check global scope for recent data (< 2 mins)
        # Refactor Phase 2: Use DatastoreManager.get_artifact
        entry = DatastoreManager.get_artifact(norm_ticker, "history", interval)
        if entry:
            # [STABILITY] Accept data up to 120s old for immediate resonance
            age_sec = (datetime.now() - entry["updated_at"]).total_seconds()
            if age_sec < 120:
                logger.info(f"VLI Fast-Path: Warm cache hit for {norm_ticker} (Age: {age_sec:.1f}s)")
                
                data_val = entry["data"]
                # If data is a dict (Phase 3 storage), extract the price
                if isinstance(data_val, dict):
                    price_val = data_val.get("raw", {}).get("Close")
                    if price_val:
                        return {"symbol": norm_ticker, "price": price_val, "change": 0.0, "is_cached": True}
                
                # Fallback to regex for string-based cache
                try:
                    price_val = float(re.search(r"Close\*\*: (\d+\.?\d*)", str(data_val)).group(1))
                    return {"symbol": norm_ticker, "price": price_val, "change": 0.0, "is_cached": True}
                except Exception:
                    pass  # Fall through to fetch if parse fails

        # 2. Fast-Fetch Phase: Bypassing the global throttle lock for single-ticker quotes
        # [REPLAY_INSTRUMENTATION] Bypass Fast-Path for Replay Mode to ensure temporal sync
        from src.utils.temporal import get_effective_now
        is_replay = abs((datetime.now() - get_effective_now()).total_seconds()) > 5
        
        if use_fast_path and not is_replay:
            logger.info(f"VLI Fast-Path: Starting lock-free fast-fetch for {norm_ticker}")
            try:
                # [STABILITY] 5s hard-timeout for all data retrieval threads
                t_obj = await asyncio.wait_for(asyncio.to_thread(yfinance.Ticker, norm_ticker, session=_get_session()), timeout=5.0)
                # Use faster 'fast_info' instead of full history
                fast = t_obj.fast_info

                if fast is not None and hasattr(fast, "last_price") and fast.last_price:
                    return {
                        "symbol": norm_ticker,
                        "price": fast.last_price,
                        "change": ((fast.last_price / fast.previous_close) - 1) * 100 if hasattr(fast, "previous_close") and fast.previous_close else 0.0,
                        "volume": getattr(fast, "last_volume", 0),
                        "is_fast_fetch": True,
                    }
                else:
                    logger.info(f"VLI: Fast-info empty for {norm_ticker}, falling back to batched history.")
            except Exception as fe:
                logger.warning(f"Fast-fetch failed for {norm_ticker}, falling back to batched fetch: {fe}")

        # 3. Standard Batched Fetch (Tier 3 fallback)
        # [REPLAY_INSTRUMENTATION] Expand window to 10d for Replay to survive weekends
        period = "10d" if is_replay else period
        data = await asyncio.wait_for(asyncio.to_thread(_fetch_batch_history, [norm_ticker], period, interval), timeout=5.0)

        # Extract using normalized ticker to ensure level-0 match
        ticker_df = _extract_ticker_data(data, norm_ticker)

        if ticker_df.empty:
            return f"[ERROR]: No data found for ticker '{ticker}' (normalized: {norm_ticker})."

        # [STABILITY] Filter out "Ghost Rows" (partial NaNs at Market Close)
        # We need at least 'Close' and 'Volume' or 'Open' to consider a row valid
        stable_df = ticker_df.dropna(subset=[col for col in ticker_df.columns if col.lower() in ["close", "adj close", "volume", "open"]], how="all")
        if stable_df.empty:
            return f"[ERROR]: No stable data points found for '{ticker}'."
            
        last_row = stable_df.iloc[-1]

        # Case-Insensitive Column Resolution
        def _get_val(row, keys):
            for k in keys:
                if k in row.index: return float(row[k])
                if k.lower() in row.index: return float(row[k.lower()])
                if k.capitalize() in row.index: return float(row[k.capitalize()])
            return None

        quote_price = _get_val(last_row, ["Close", "Adj Close"])
        if quote_price is None:
            return f"[ERROR]: Could not find price column for '{ticker}'. Columns: {list(last_row.index)}"

        prev_close = _get_val(last_row, ["Open"]) # Fallback for change calc if only 1 day
        if len(stable_df) > 1:
            prev_close = _get_val(stable_df.iloc[-2], ["Close", "Adj Close"])

        return {
            "symbol": norm_ticker,
            "original_ticker": ticker.upper(),
            "price": quote_price,
            "high": float(last_row["High"]),
            "low": float(last_row["Low"]),
            "volume": int(last_row["Volume"]),
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except TimeoutError:
        logger.error(f"Timeout fetching quote for {ticker}")
        return "[ERROR]: Data retrieval timed out (15s)."
    except Exception as e:
        logger.error(f"Error fetching quote for {ticker}: {e}")

        # [NEW] Snapper Data Fallback (Finviz)
        logger.info(f"VLI_SYSTEM: YFinance failed for {ticker}. Deploying Snapper Data Fallback (Finviz)...")
        try:
            # Try to get structured data from Finviz first
            fin_quotes = await fetch_finviz_quotes([norm_ticker])
            if norm_ticker.upper() in [k.upper() for k in fin_quotes.keys()]:
                quote = fin_quotes[norm_ticker.upper()]
                return {
                    "symbol": norm_ticker,
                    "price": quote["price"],
                    "volume": quote["volume"],
                    "source": f"Finviz {quote['source']} (Fallback)",
                    "note": f"[VLI_SYSTEM] YFinance failed ({str(e)}). Sucessfully extracted via Finviz scraper.",
                }

            # If data extraction fails, fall back to the absolute last resort: Visual Snapshot
            logger.info(f"VLI_SYSTEM: Finviz extraction failed for {ticker}. Falling back to Visual TradingView Snapshot.")
            # Format the TradingView chart URL (Symbol must be correct for TV)
            # Remove prefixes/suffixes for clean TV lookup
            tv_symbol = norm_ticker.replace("^", "").split(".")[0]
            tv_url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}"

            # Use the tool to get the snapshot - reaching for coroutine safely
            tool_fn = getattr(snapper, "coroutine", getattr(snapper, "func", None))
            if tool_fn:
                snap_json = await tool_fn(url=tv_url)
            else:
                snap_json = await snapper.invoke({"url": tv_url})

            import json

            snap_res = json.loads(snap_json)

            if isinstance(snap_res, dict) and "images" in snap_res:
                return {
                    "symbol": norm_ticker,
                    "price": "SEE_IMAGE",
                    "source": "Visual TradingView Snapshot (Fallback)",
                    "note": f"[VLI_SYSTEM] Data retrieval failed ({str(e)}). Headless chart captured for visual analysis.",
                    "images": snap_res["images"],
                }
            else:
                err_msg = snap_res.get("error", "Unknown Error") if isinstance(snap_res, dict) else str(snap_res)
                return f"[ERROR]: Primary fetch failed ({str(e)}) AND Visual Fallback returned invalid data: {err_msg}"
        except Exception as fe:
            import traceback

            tb = traceback.format_exc()
            logger.error(f"Fallback also failed: {fe}\n{tb}")
            return f"[ERROR]: Primary fetch failed ({str(e)}) and Visual Fallback failed ({str(fe)}). Check system logs for traceback."


@tool
async def get_sharpe_ratio(ticker: str) -> str:
    """
    Technical Analysis: Calculate the Sharpe Ratio for a given ticker based on last 252 trading days.
    """
    try:
        df = await asyncio.to_thread(_fetch_stock_history, ticker, "1y", "1d")
        if df.empty:
            return f"[ERROR]: No data for {ticker}"

        returns = df["Close"].pct_change().dropna()
        if len(returns) < 50:
            return "Insufficient data for Sharpe calculation."

        sharpe = (returns.mean() / returns.std()) * (252**0.5)
        return f"Sharpe Ratio ({ticker}): {sharpe:.2f}"
    except Exception as e:
        return f"[ERROR]: {str(e)}"


@tool
async def get_sortino_ratio(ticker: str) -> str:
    """
    Technical Analysis: Calculate the Sortino Ratio (downside risk-adjusted) for a given ticker.
    """
    try:
        df = await asyncio.to_thread(_fetch_stock_history, ticker, "1y", "1d")
        if df.empty:
            return f"[ERROR]: No data for {ticker}"

        returns = df["Close"].pct_change().dropna()
        if len(returns) < 20:
            return "Insufficient data for Sortino calculation."

        MAR = 0.0  # Minimum Acceptable Return (daily)
        downside = returns - MAR
        downside_squared = downside[downside < 0] ** 2
        downside_deviation = (downside_squared.sum() / len(returns)) ** 0.5

        if downside_deviation == 0:
            return f"Sortino Ratio ({ticker}): N/A (No downside volatility)"

        sortino = ((returns.mean() - MAR) / downside_deviation) * (252**0.5)
        return f"Sortino Ratio ({ticker}): {sortino:.2f}"
    except Exception as e:
        return f"[ERROR]: {str(e)}"


@tool
async def run_smc_analysis(ticker: str, interval: str = "auto") -> str:
    """
    SMC Specialist Primitive: Executes a professional ICT-based analysis using Multi-Timeframe Alignment
    by default (interval='auto'). If a specific interval is provided (e.g. '1h'), it will execute a
    single-pass isolated scanner.
    """
    from datetime import datetime

    norm_ticker = _normalize_ticker(ticker)
    # Refactor Phase 2: Use DatastoreManager
    entry = DatastoreManager.get_artifact(norm_ticker, "smc_analysis", interval)
    if entry:
        logger.info(f"[ANALYSIS_CACHE HIT] Reusing cached SMC analyst report for {norm_ticker}")
        return entry["data"]

    import os
    import sys

    try:
        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        try:
            from smartmoneyconcepts import smc
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout
    except ImportError:
        return "[ERROR]: The 'smartmoneyconcepts' library is required. Run 'pip install smartmoneyconcepts'."

    # Load configuration
    from src.config.smc_loader import load_smc_config

    config = load_smc_config()
    strategy = config.get("smc_strategy", {})

    norm_ticker = _normalize_ticker(ticker)

    # ==========================================
    # FALLBACK: Isolated Single-Pass Execution
    # ==========================================
    if interval.lower() != "auto":
        interval_norm = interval.lower()
        if interval_norm in ["1m", "2m", "5m", "15m"]:
            swing_length, period_needed = 20, "10d"
        elif interval_norm in ["1h", "4h", "2h"]:
            swing_length, period_needed = 10, "1mo"
        elif interval_norm in ["1d", "1wk"]:
            swing_length, period_needed = 5, "1y"
        else:
            swing_length, period_needed = 10, "1mo"

        history_samples = max(swing_length * 3, 100)
        logger.info(f"VLI SMC Analyst [CUSTOM OVERRIDE]: Executing {ticker} @ {interval}")

        try:
            # [REPLAY_INSTRUMENTATION]
            ref_time = get_effective_now()
            is_replay = (ref_time.date() < datetime.now().date())
            
            if is_replay:
                data = await asyncio.wait_for(asyncio.to_thread(_fetch_replay_history, [norm_ticker], period_needed, interval, end_date=ref_time), timeout=10.0)
            else:
                data = await asyncio.wait_for(asyncio.to_thread(_fetch_batch_history, [norm_ticker], period_needed, interval), timeout=10.0)
            
            full_df = _extract_ticker_data(data, norm_ticker)
            if full_df.empty or len(full_df) < 10:
                return f"### {ticker} Analysis @ {interval}\n- [ERROR]: Insufficient data."

            df = full_df.tail(history_samples).copy()
            df.columns = [c.lower() for c in df.columns]

            # [STRUCTURAL_INTEGRITY] Use Adjusted Data for Structural Detection
            df_calc = df.copy()
            if "adj close" in df.columns:
                mask = df["close"] > 0
                df_calc.loc[mask, "adj_ratio"] = df["adj close"] / df["close"]
                df_calc.loc[~mask, "adj_ratio"] = 1.0
                for col in ["open", "high", "low", "close"]:
                    df_calc[col] = df[col] * df_calc["adj_ratio"]
            
            # Execute on adjusted data
            swings = smc.swing_highs_lows(df_calc, swing_length=swing_length)
            fvg = smc.fvg(df_calc)
            ob = smc.ob(df_calc, swings)
            structure = smc.bos_choch(df_calc, swings)

            fvg_count = len(fvg[fvg["FVG"].fillna(0) != 0]) if "FVG" in fvg.columns else 0
            ob_count = len(ob[ob["OB"].fillna(0) != 0]) if "OB" in ob.columns else 0

            report = [f"## Custom Single-Pass SMC Analysis: {ticker} ({interval})", ""]
            last = df.iloc[-1]
            report.append(f"- **OHLC**: O: `{last['open']:.2f}` | H: `{last['high']:.2f}` | L: `{last['low']:.2f}` | C: `{last['close']:.2f}` | V: `{last['volume']}`")

            last_struct = structure.iloc[-1]
            if last_struct.get("CHOCH") or last_struct.get("choch"):
                report.append("- **State**: ⚡ **Change of Character (ChoCh)** detected.")
            elif last_struct.get("BOS") or last_struct.get("bos"):
                report.append("- **State**: 📈 **Break of Structure (BOS)** confirmed.")
            else:
                report.append("- **State**: ⚖️ Stable market structure.")

            report.append(f"- **Order Blocks**: {ob_count} mapped.")
            report.append(f"- **FVGs**: {fvg_count} mapped.")
            report.append(f"\n**Current Price**: `${df['close'].iloc[-1]:.2f}`")
            return "\n".join([str(r) for r in report])
        except Exception as e:
            return f"[ERROR]: Single-pass failed: {e}"

    # ==========================================
    # APEX 500 AUTONOMOUS MTF SCANNER
    # ==========================================
    logger.info(f"VLI SMC Analyst [MTF AUTONOMOUS SCAN]: Executing Apex 500 Alignment for {ticker}")
    report = [f"## MTF SMC Alignment Scan: {ticker} (Apex 500 Scanner)", ""]

    macro_bias = "Neutral"

    # Load configurations for the scanner
    macro_cfg = strategy.get("macro_map", {})
    tactical_cfg = strategy.get("tactical_map", {})
    trigger_cfg = strategy.get("execution_trigger", {})

    macro_lookback = macro_cfg.get("lookback_bars", 200)
    tactical_lookback = tactical_cfg.get("lookback_bars", 100)
    trigger_lookback = trigger_cfg.get("execution_lookback", 50)

    # [REPLAY_INSTRUMENTATION] Era-Detection & Adaptive Scaling
    ref_time = get_effective_now()
    is_deep_history = (datetime.now() - ref_time).days > 700
    
    if is_deep_history:
        logger.info(f"VLI_REPLAY: Entering Deep History Structural Mode (Origin: {ref_time})")
        macro_tf, macro_period = "1mo", "10y"
        tactical_tf, tactical_period = "1wk", "2y"
        trigger_tf, trigger_period = "1d", "1y"
        report[0] = f"## MTF SMC Structural Replay: {ticker} (Legacy Analysis Mode)"
        report.append("> [!NOTE]\n> Intraday tactical data is substituted with Weekly/Daily structural pivots due to historical sampling limits (>2 years).")
    else:
        # Standard Configuration
        macro_tf = macro_cfg.get("timeframes", ["1d"])[0]
        macro_period = "1y" if macro_tf in ("1d", "4h") else "6mo"
        tactical_tf = tactical_cfg.get("timeframes", ["1h"])[0]
        tactical_period = "1mo"
        trigger_tf = trigger_cfg.get("timeframes", ["5m"])[0]
        trigger_period = "5d"
        trigger_period = "5d"

    # === CONCURRENT FETCH PHASE ===
    async def fetch_with_sem(period, tf):
        async with _get_yf_semaphore():
            return await asyncio.wait_for(asyncio.to_thread(_fetch_stock_history, norm_ticker, period, tf), timeout=12.0)

    results = await asyncio.gather(
        fetch_with_sem(macro_period, macro_tf), 
        fetch_with_sem(tactical_period, tactical_tf), 
        fetch_with_sem(trigger_period, trigger_tf), 
        return_exceptions=True
    )
    mData_res, tData_res, trData_res = results

    try:
        if isinstance(mData_res, Exception):
            raise mData_res
        mDF = mData_res.tail(macro_lookback).copy()
        m_struct_detail = ""
        if not mDF.empty:
            mDF.columns = [c.lower() for c in mDF.columns]
            mSwings = smc.swing_highs_lows(mDF, swing_length=15)
            mStruct = smc.bos_choch(mDF, mSwings)

            latest_bos = mStruct[mStruct["BOS"].fillna(0) != 0].tail(1)
            latest_choch = mStruct[mStruct["CHOCH"].fillna(0) != 0].tail(1)

            # Simple bias heuristic based on the latest structural event
            if not latest_choch.empty:
                macro_bias = "Bullish" if latest_choch["CHOCH"].iloc[-1] == 1 else "Bearish"
                m_level = latest_choch["Level"].iloc[-1] if "Level" in latest_choch.columns else 0
                m_struct_detail = f" (CHoCH at `{m_level:.4f}`)"
            elif not latest_bos.empty:
                macro_bias = "Bullish" if latest_bos["BOS"].iloc[-1] == 1 else "Bearish"
                m_level = latest_bos["Level"].iloc[-1] if "Level" in latest_bos.columns else 0
                m_struct_detail = f" (BOS at `{m_level:.4f}`)"

        report.append(f"### 1. Macro Map ({macro_tf})")
        report.append(f"- **Institutional Trend**: {macro_bias}{m_struct_detail}")
        if not mDF.empty:
            l = mDF.iloc[-1]
            report.append(f"- **OHLC**: O: `{l['open']:.2f}` | H: `{l['high']:.2f}` | L: `{l['low']:.2f}` | C: `{l['close']:.2f}` | V: `{l['volume']}`")
    except Exception as e:
        report.append(f"### 1. Macro Map ({macro_tf})\n- [ERROR]: {e}")
        macro_bias = "Error"

    # 2. Tactical Map (Zones)
    tactical_ready = False
    try:
        if isinstance(tData_res, Exception):
            raise tData_res
        tDF = tData_res.tail(tactical_lookback).copy()
        if not tDF.empty:
            tDF.columns = [c.lower() for c in tDF.columns]
            tSwings = smc.swing_highs_lows(tDF, swing_length=10)
            tOB = smc.ob(tDF, tSwings)
            tFVG = smc.fvg(tDF)

            ob_c = len(tOB[tOB["OB"].fillna(0) != 0]) if "OB" in tOB.columns else 0
            fvg_c = len(tFVG[tFVG["FVG"].fillna(0) != 0]) if "FVG" in tFVG.columns else 0
            tactical_ready = ob_c > 0 or fvg_c > 0

            report.append(f"### 2. Tactical Map ({tactical_tf})")
            report.append(f"- **Zones Mapped**: {ob_c} Order Blocks | {fvg_c} Fair Value Gaps.")
            l = tDF.iloc[-1]
            report.append(f"- **OHLC**: O: `{l['open']:.2f}` | H: `{l['high']:.2f}` | L: `{l['low']:.2f}` | C: `{l['close']:.2f}` | V: `{l['volume']}`")

            if ob_c > 0:
                last_ob = tOB[tOB["OB"].fillna(0) != 0].iloc[-1]
                dir_str = "Bullish (Demand)" if last_ob["OB"] == 1 else "Bearish (Supply)"
                report.append(f"- **Active Order Block**: {dir_str} at `{last_ob['Bottom']:.4f}` - `{last_ob['Top']:.4f}`")

            if fvg_c > 0:
                last_fvg = tFVG[tFVG["FVG"].fillna(0) != 0].iloc[-1]
                dir_str = "Bullish (Imbalance)" if last_fvg["FVG"] == 1 else "Bearish (Imbalance)"
                report.append(f"- **Active FVG**: {dir_str} at `{last_fvg['Bottom']:.4f}` - `{last_fvg['Top']:.4f}`")
        else:
            report.append(f"### 2. Tactical Map ({tactical_tf})\n- Insufficient Data")
    except Exception as e:
        report.append(f"### 2. Tactical Map ({tactical_tf})\n- [ERROR]: {e}")

    # 3. Execution Trigger (Liquidity)
    sweep_aligned = False
    try:
        if isinstance(trData_res, Exception):
            raise trData_res
        trDF = trData_res.tail(trigger_lookback).copy()
        if not trDF.empty:
            trDF.columns = [c.lower() for c in trDF.columns]
            trSwings = smc.swing_highs_lows(trDF, swing_length=5)
            # liquidity is tracked against swings
            trLiq = smc.liquidity(trDF, trSwings)

            liq_event = trLiq[trLiq["Liquidity"].fillna(0) != 0].tail(1)
            if not liq_event.empty:
                # 1 = Bullish Sweep (Sell-side liquidity grabbed), -1 = Bearish Sweep
                sweep_dir = "Bullish" if liq_event["Liquidity"].iloc[-1] == 1 else "Bearish"
                # Check MTF alignment
                if sweep_dir == macro_bias:
                    sweep_aligned = True

                swept_price = liq_event["Level"].iloc[-1] if "Level" in liq_event.columns else 0

                report.append(f"### 3. Execution Trigger ({trigger_tf})")
                l = trDF.iloc[-1]
                report.append(f"- **OHLC**: O: `{l['open']:.2f}` | H: `{l['high']:.2f}` | L: `{l['low']:.2f}` | C: `{l['close']:.2f}` | V: `{l['volume']}`")
                report.append(f"- **Liquidity Sweep**: YES ({sweep_dir}) at `{swept_price:.4f}`")
            else:
                report.append(f"### 3. Execution Trigger ({trigger_tf})")
                l = trDF.iloc[-1]
                report.append(f"- **OHLC**: O: `{l['open']:.2f}` | H: `{l['high']:.2f}` | L: `{l['low']:.2f}` | C: `{l['close']:.2f}` | V: `{l['volume']}`")
                report.append("- **Liquidity Sweep**: NO (Accumulating)")
    except Exception as e:
        report.append(f"### 3. Execution Trigger ({trigger_tf})\n- [ERROR]: {e}")

    # 4. Authorization Matrix
    report.append("### 4. Apex Authorization Matrix")
    if sweep_aligned and tactical_ready:
        report.append("- **Status**: **[PASS]** Execution trigger aligns with MTF Institutional Macro trend.")
    else:
        report.append("- **Status**: **[FAIL]** Trigger does not align with Macro trend, or missing tactical structural zones.")

    final_report = "\n".join([str(r) for r in report])
    
    # Phase 3 Integration: Store the analysis in the persistent cache
    # We use the macro timeframe's last price as the reference for drift monitoring
    current_price = 0.0
    try:
        # mData_res contains the macro dataframe (1d or similar)
        if not mData_res.empty:
            current_price = float(mData_res.iloc[-1]["Close"])
    except:
        pass
        
    DatastoreManager.store_artifact(
        ticker=norm_ticker,
        resource_type="smc_analysis",
        timeframe=interval,
        data=final_report,
        price=current_price if current_price > 0 else None
    )

    return final_report


async def get_raw_smc_tables(ticker: str, interval: str = "1d", period: str = "1y") -> str:
    """
    Headless Data Engine - Raw Data Tables Override
    Bypasses text synthesis and returns pure computational pandas structures as JSON.
    """
    import json
    from datetime import datetime

    norm_ticker = ticker.upper()

    cache_key = f"{norm_ticker}_{period}_{interval}_raw"
    analysis_cache = DatastoreManager.get_analysis_cache()

    if cache_key in analysis_cache:
        entry = analysis_cache[cache_key]
        if "last_updated" in entry and "data" in entry:
            age_sec = (datetime.now() - entry["last_updated"]).total_seconds()
            ttl = _get_ttl_seconds(interval)
            if age_sec < ttl:
                logger.info(f"[ANALYSIS_CACHE HIT] Reusing fast headless SMC data for {norm_ticker} (Age: {age_sec:.1f}s)")
                return entry["data"]

    try:
        data = await asyncio.wait_for(asyncio.to_thread(_fetch_stock_history, norm_ticker, period, interval), timeout=15.0)
        df = data.tail(100).copy()
        if df.empty:
            return json.dumps([{"error": f"No historical market data retrieved for {norm_ticker}. Ensure the ticker symbol is valid and active. (Syntax hint: Use the '$' prefix like $AAPL to bypass sentence tokenization errors)."}])

        df.columns = [c.lower() for c in df.columns]
        # Compute pure primitive arrays
        from smartmoneyconcepts import smc

        swings = smc.swing_highs_lows(df, swing_length=15)
        structure = smc.bos_choch(df, swings)
        fvg = smc.fvg(df)
        ob = smc.ob(df, swings)

        # Timeline merge wrapper
        df["swing"] = swings["HighLow"] if "HighLow" in swings else None
        df["bos"] = structure["BOS"] if "BOS" in structure else None
        df["choch"] = structure["CHOCH"] if "CHOCH" in structure else None

        # For memory constraints, only return the last 20 blocks
        export_df = df.tail(20).copy()

        # Serialize datetime indexes safely
        import pandas as pd

        export_df.reset_index(inplace=True)
        for col in export_df.columns:
            if pd.api.types.is_datetime64_any_dtype(export_df[col]):
                export_df[col] = export_df[col].dt.strftime("%Y-%m-%d %H:%M:%S")

        # Drop NaN bounds
        export_df = export_df.fillna("None")

        final_json = json.dumps({"ticker": norm_ticker, "type": "RAW_SMC_PRICE_ACTION_TABLE", "timeframe": interval, "data": json.loads(export_df.to_json(orient="records"))})

        # Phase 3 Integration: Store the raw data in the persistent cache
        # We use the last Close price as the reference for drift monitoring
        current_price = float(df["close"].iloc[-1])
        DatastoreManager.store_artifact(
            ticker=norm_ticker,
            resource_type="smc_analysis",
            timeframe=interval + "_raw",
            data=final_json,
            price=current_price
        )
        return final_json
    except Exception as e:
        import traceback

        return json.dumps([{"error": f"Raw Table Error: {str(e)}"}])


def _calculate_sortino_ratio(ticker_df: pd.DataFrame, risk_free_rate: float = 0.0) -> float:
    """
    Calculates the annualized Sortino Ratio for a given ticker DataFrame.
    Sortino = (R_p - R_f) / DownsideDev
    """
    try:
        # Use 'Close' or 'adj close' for returns
        col = "Close" if "Close" in ticker_df.columns else "close"
        if col not in ticker_df.columns: return 0.0
        
        returns = ticker_df[col].pct_change().dropna()
        if returns.empty: return 0.0
        
        # Annualization factor (Daily to Annual)
        # Assuming Daily data (1d)
        mean_return = returns.mean() * 252
        
        # Downside Deviation: Std Dev of negative returns only
        downside_returns = returns[returns < risk_free_rate]
        if downside_returns.empty: return 0.0 # No downside risk detected? 
        
        # Note: We calculate variance using N (len(returns)) not len(downside_returns) 
        # for a standard Sortino calculation.
        downside_dev = np.sqrt((downside_returns**2).sum() / len(returns)) * np.sqrt(252)
        
        if downside_dev == 0: return 0.0
        
        return (mean_return - risk_free_rate) / downside_dev
    except Exception as e:
        logger.error(f"VLI_ECON: Sortino calculation failed: {e}")
        return 0.0

@tool
async def get_macro_symbols(fast_update: bool = False) -> str:
    """
    Institutional Macro Registry Tool: Fetches the current states of all registered macro indicators
    (Indices, Yields, Commodities, Crypto). 
    
    If fast_update=True: Returns only Price, Vol, Change (15s heartbeat).
    If fast_update=False: Returns full analysis including Sortino Ratio and Level Analysis (5m cycle).
    """
    from src.services.macro_registry import macro_registry
    from datetime import datetime
    import json
    import os

    macros = macro_registry.get_macros()
    results = {}
    rows = []

    # Batch fetch using the datastore infrastructure
    ticker_list = list(macros.values())
    logger.info(f"VLI_SYSTEM: Fetching batch macro data for: {ticker_list}")
    try:
        # [REPLAY_INSTRUMENTATION] Replay-Aware Sparkline Fetch
        ref_time = get_effective_now()
        
        # [MARKET_ANCHOR] Removed so futures reflect real-time trailing 100 minutes.
        logger.info(f"VLI_SYSTEM: Using direct trailing time for Sparkline target: {ref_time}")
        
        is_replay = abs((datetime.now() - ref_time).total_seconds()) > 5

        # [SPARKLINE_INTERVAL_LOCK] Fetch 1m data directly, bypassing Replay delegate
        # yfinance is notoriously buggy with end=... for intraday 1m data, causing full-day omissions.
        async def _fetch_direct_sparkline():
            def _do_fetch():
                return yfinance.download(
                    ticker_list,
                    period="2d",
                    interval="1m",
                    progress=False,
                    threads=False,
                    timeout=15.0,
                    auto_adjust=False,
                    prepost=True
                )
            async with _get_yf_semaphore():
                res = await asyncio.to_thread(_do_fetch)
            if res is not None and not res.empty:
                # [TZ_ALIGNMENT] Force identical timezone across all tickers
                try:
                    res.index = pd.to_datetime(res.index, utc=True).tz_convert('America/New_York').tz_localize(None)
                except Exception:
                    res.index = pd.to_datetime(res.index).tz_localize(None)
                return res
            return pd.DataFrame()
            
        # High-Fidelity Data Retrieval (2-Day 1M window for sub-second anchoring)
        tasks = [
            asyncio.to_thread(_fetch_batch_history, ticker_list, "5d", "1d"),
            _fetch_direct_sparkline()
        ]
        if not fast_update:
            tasks.append(asyncio.to_thread(_fetch_batch_history, ticker_list, "60d", "1d"))
            
        results_raw = await asyncio.wait_for(asyncio.gather(*tasks), timeout=25.0)
        data_1d = results_raw[0]
        data_5m = results_raw[1]
        data_30d = results_raw[2] if len(results_raw) > 2 else None
        
        # [MEMORY_ANCHOR] Precise Slice for Sparkline Temporal Alignment
        try:
            if not data_5m.empty:
                safe_index = data_5m.index
                if getattr(safe_index, 'tz', None) is not None:
                     safe_index = safe_index.tz_convert('America/New_York').tz_localize(None)
                data_5m = data_5m[safe_index <= pd.Timestamp(ref_time).tz_localize(None)]
        except Exception as filter_err:
             logger.warning(f"VLI: In-memory anchor filter failed: {filter_err}")

        for label, ticker in macros.items():
            ticker_df = _extract_ticker_data(data_1d, ticker)
            
            # Fallback: If batch fetch failed for this specific ticker, try individual fetch
            if ticker_df.empty:
                logger.info(f"VLI: Batch fetch missing {ticker}, falling back to individual lookup.")
                try:
                    ticker_df = await asyncio.to_thread(_fetch_batch_history, [ticker], "5d", "1d")
                    ticker_df = _extract_ticker_data(ticker_df, ticker)
                except Exception as fe:
                    logger.error(f"VLI: Fallback fetch failed for {ticker}: {fe}")

            if ticker_df.empty:
                results[label] = {"symbol": ticker, "status": "Error (No Data)"}
                continue

            last_row = ticker_df.iloc[-1]
            prev_row = ticker_df.iloc[-2] if len(ticker_df) > 1 else last_row
            
            try:
                # Handle pandas Series duplication gracefully
                p_c = last_row["Close"] if "Close" in last_row else last_row["close"]
                price = float(p_c.iloc[0]) if isinstance(p_c, pd.Series) else float(p_c)
                
                p_p = prev_row["Close"] if "Close" in prev_row else prev_row["close"]
                prev_price = float(p_p.iloc[0]) if isinstance(p_p, pd.Series) else float(p_p)
                
                change = ((price / prev_price) - 1) * 100
            except Exception as pe:
                logger.error(f"VLI: Price parse failed: {pe}")
                price = 0.0
                change = 0.0

            # [SPARKLINE_EXTRACTION] High-Fidelity 1M Scaling (390m trading session)
            sparkline_df = _extract_ticker_data(data_5m, ticker)
            
            # Fallback for individual missing 1m data due to batch merging quirks (futures vs crypto)
            if sparkline_df.empty or sparkline_df.isna().all().all():
                try:
                    logger.info(f"VLI: Batch 1m empty for {ticker}, fetching individually.")
                    sdf = await asyncio.to_thread(yfinance.download, ticker, period="2d", interval="1m", prepost=True, progress=False, threads=False)
                    if sdf is not None and not sdf.empty:
                        try:
                            sdf.index = pd.to_datetime(sdf.index, utc=True).tz_convert('America/New_York').tz_localize(None)
                        except Exception:
                            sdf.index = pd.to_datetime(sdf.index).tz_localize(None)
                        sparkline_df = sdf
                except Exception as ef:
                    logger.warning(f"VLI: Fallback 1m fetch failed for {ticker}: {ef}")

            sparkline_values = _bucket_sparkline_data(sparkline_df, ref_time, price, num_points=32, span_minutes=240)

            # [RISK_METRICS] Sortino Ratio (30d)
            sortino = 0.0
            if data_30d is not None:
                ticker_30d = _extract_ticker_data(data_30d, ticker)
                sortino = _calculate_sortino_ratio(ticker_30d)

            results[label] = {
                "symbol": ticker,
                "price": round(price, 4),
                "change_pct": round(change, 2),
                "sortino": round(sortino, 2),
                "volume": int(last_row["Volume"].iloc[0]) if "Volume" in last_row and isinstance(last_row["Volume"], pd.Series) else (int(last_row["Volume"]) if "Volume" in last_row else 0),
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # [STRUCTURAL_JSON] Format for DynamicTable Component
            # Headers: ["Asset", "Ticker", "Price", "Change %", "Sortino", "Trend (5m)"]
            # [YIELD_FORMATTING] Yields must be in % not $
            is_yield = any(y in ticker.upper() for y in ["TNX", "TYX", "FVX", "BX", "IRX"])
            price_display = f"{price:.2f}%" if is_yield else f"${price:,.2f}"
            
            from src.tools.macros import MACRO_NAMES
            
            # Resolve descriptive name for UI
            display_name = MACRO_NAMES.get(label, label)
            if display_name == label and label.upper() == "CL":
                display_name = "WTI Crude Oil"

            rows.append([
                display_name,
                ticker,
                price_display,
                {"value": round(change, 2), "type": "text"},
                round(sortino, 2),
                {"type": "sparkline", "value": sparkline_values}
            ])

        # Create Structural Response Object
        response_obj = {
            "type": "table",
            "headers": ["Asset", "Ticker", "Price", "Change %", "Sortino", "Trend (5m)"],
            "rows": rows,
            "metadata": {
                "origin": str(ref_time),
                "is_replay": is_replay,
                "is_fast_pulsar": fast_update,
                "source": "VLI_DATA_ENGINE_V2"
            }
        }

        # Create Artifact for persistence
        artifact_path = os.path.join("data", "artifacts", "get_macro_symbols.json")
        os.makedirs(os.path.dirname(artifact_path), exist_ok=True)
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(response_obj, f, indent=4)

        # [NEW] Synchronize to VLI Transit Bucket (Dashboard Feed)
        from src.config.vli import get_vli_path
        transit_path = get_vli_path(os.path.join("01_Transit", "Buckets", "MACRO_WATCHLIST_state.json"))
        try:
            os.makedirs(os.path.dirname(transit_path), exist_ok=True)
            with open(transit_path, "w", encoding="utf-8") as f:
                json.dump(response_obj, f, indent=4)
            logger.info(f"VLI_SYSTEM: Macro state synchronized to transit bucket: {transit_path}")
        except Exception as te:
            logger.error(f"VLI_SYSTEM: Failed to sync macro state: {te}")

        return json.dumps(response_obj)

    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Macro Tool Error: {e}")
        return f"[ERROR]: Failed to fetch macro indicators: {str(e)}"


@tool
async def get_macro_regime(ticker: str) -> str:
    """
    Evaluates the basic macro regime for a given ticker or index.
    Currently specifically tuned for $VIX monitoring.
    """
    try:
        norm_ticker = _normalize_ticker(ticker)
        # Use fast fetch for quotes
        data = await get_stock_quote.ainvoke({"ticker": norm_ticker, "use_fast_path": True, "force_refresh": False})
        if isinstance(data, dict) and "price" in data:
            price = data["price"]
            # Visual fallback could result in 'SEE_IMAGE'
            if isinstance(price, (int, float)):
                if norm_ticker == "^VIX":
                    if price > 20.0:
                        return "STRESS"
                    elif price < 15.0:
                        return "COMPLACENT"
                    else:
                        return "NORMAL"
                
                # Generalized naive fallback
                change = data.get("change", 0)
                if isinstance(change, (int, float)):
                    if change > 1.0:
                        return "BULLISH"
                    elif change < -1.0:
                        return "BEARISH"
                return "NEUTRAL"
        return "UNKNOWN"
    except Exception as e:
        logger.error(f"Regime Tool Error: {e}")
        return f"[ERROR]: {str(e)}"


@tool
async def get_sparkline_audit_vli(ticker: str, ref_time_ms: int = None) -> str:
    """
    High-Fidelity Audit Engine: Returns 30 strictly sampled ground-truth quotes.
    Phase-locks to ref_time_ms if provided to ensure dashboard alignment.
    """
    import json
    from datetime import datetime, timedelta
    import pandas as pd
    from src.utils.temporal import get_effective_now
    
    norm_ticker = _normalize_ticker(ticker)
    
    # [PHASE_LOCK] Synchronize with the dashboard's last refresh point
    if ref_time_ms:
        ref_time = datetime.fromtimestamp(ref_time_ms / 1000.0)
    else:
        ref_time = get_effective_now()
    
    try:
        # Fetch 1m data for high-precision 10m sampling
        data = await asyncio.wait_for(asyncio.to_thread(_fetch_batch_history, [norm_ticker], "5d", "1m"), timeout=15.0)
        df = _extract_ticker_data(data, norm_ticker)
        
        if df.empty:
            return json.dumps({"error": f"No ground truth for {ticker}"})
            
        current_price = float(df.iloc[-1]["Close"] if "Close" in df.columns else df.iloc[-1]["close"])
        # Audit sync: 20 points over 390m trading session
        audit_values = _bucket_sparkline_data(df, ref_time, current_price, num_points=20, span_minutes=100)
        
        interval = 390.0 / 19.0
        audit_results = []
        for i, val in enumerate(audit_values):
            target_time = ref_time - timedelta(minutes=(19-i)*interval)
            audit_results.append({
                "time": target_time.strftime("%m-%d %H:%M"),
                "price": val
            })

        return json.dumps({
            "ticker": ticker,
            "ref_time": ref_time.isoformat(),
            "points": audit_results
        })
                
        return json.dumps({
            "ticker": norm_ticker,
            "anchor_time": ref_time.strftime("%Y-%m-%d %H:%M:%S"),
            "points": audit_results
        })
        
    except Exception as e:
        logger.error(f"Audit Tool Error: {e}")
        return json.dumps({"error": str(e)})

@tool
async def manage_macro_watchlist(action: str, label: str = None, ticker: str = None) -> str:
    """
    Administrative Watchlist Manager: Allows for dynamic and persistent modification 
    of the Macro Registry.
    
    Actions:
    - 'add': Requires both label and ticker. (e.g., 'Gold', 'GC=F')
    - 'remove': Requires label.
    - 'reset': Wipes all customizations and restores institutional factory defaults.
    """
    try:
        from src.services.macro_registry import macro_registry
        symbols = list(macro_registry.get_macros().values())
        logger.info(f"VLI_SYSTEM: Fetching batch macro data for: {symbols}")
        action = action.lower().strip()
        if action == "add":
            if not label or not ticker:
                return "[ERROR]: 'add' action requires both 'label' and 'ticker'."
            macro_registry.update_macro(label, ticker)
            return f"SUCCESS: Added '{label}' ({ticker}) to the persistent macro watchlist."
            
        elif action == "remove":
            if not label:
                return "[ERROR]: 'remove' action requires a 'label'."
            macro_registry.remove_macro(label)
            return f"SUCCESS: Removed '{label}' from the macro watchlist."
            
        elif action == "reset":
            macro_registry.reset_to_defaults()
            return "SUCCESS: Macro Watchlist has been factory reset to institutional defaults."
            
        else:
            return f"[ERROR]: Unsupported action '{action}'. Use 'add', 'remove', or 'reset'."
            
    except Exception as e:
        logger.error(f"Watchlist Manager Error: {e}")
        return f"[ERROR]: Failed to manage watchlist: {str(e)}"
