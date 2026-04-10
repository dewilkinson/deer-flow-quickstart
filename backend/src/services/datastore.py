# Datastore Manager for Symbol History Cache
# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

import asyncio
import logging
from datetime import datetime
from typing import Any

from langchain_core.tools import tool
from src.tools.shared_storage import history_cache, df_cache, analysis_cache, GLOBAL_CONTEXT

logger = logging.getLogger(__name__)


@tool
def invalidate_market_cache(ticker: str = "") -> str:
    """Invalidate the cache for a specific ticker or clear all cache if none provided."""
    return DatastoreManager.invalidate_cache(ticker)


@tool
def simulate_cache_volatility(force_invalid: bool = False) -> str:
    """Simulate market volatility by tweaking cache freshness or invalidating it."""
    DatastoreManager.simulate_volatility(force_invalid)
    return "Simulated cache volatility applied."


class DatastoreManager:
    _eager_worker_task = None
    _fetch_callback = None

    @classmethod
    def register_fetcher(cls, fetch_func):
        """Register the financial data fetching function to avoid circular imports."""
        cls._fetch_callback = fetch_func

    @classmethod
    def get_history_cache(cls) -> dict[str, Any]:
        from src.config.loader import get_bool_env

        if get_bool_env("VLI_CACHE_DISABLED", False):
            return {}
        return history_cache

    @classmethod
    def get_df_cache(cls) -> dict[str, Any]:
        from src.config.loader import get_bool_env

        if get_bool_env("VLI_CACHE_DISABLED", False):
            return {}
        return df_cache

    @classmethod
    def get_analysis_cache(cls) -> dict[str, Any]:
        from src.config.loader import get_bool_env

        if get_bool_env("VLI_CACHE_DISABLED", False):
            return {}
        return analysis_cache

    @classmethod
    def invalidate_cache(cls, ticker: str = "") -> str:
        """Invalidate the cache for a specific ticker or clear all."""
        caches = [history_cache, df_cache, analysis_cache]

        if not ticker:
            for c in caches:
                c.clear()
            return "Datastore cache completely flushed."

        t = ticker.upper()

        for cache in caches:
            keys_to_delete = [k for k in list(cache.keys()) if k.startswith(f"{t}_")]
            for k in keys_to_delete:
                del cache[k]

        return f"Cache invalidated for {t}."

    @classmethod
    def simulate_volatility(cls, force_invalid: bool = False):
        """Simulate market volatility by tweaking cache freshness or invalidating it."""
        caches = [history_cache, df_cache, analysis_cache]

        for cache in caches:
            for key in cache:
                # Shift age back to trigger re-fetch under tests
                if isinstance(cache[key], dict) and "last_updated" in cache[key]:
                    cache[key]["last_updated"] = datetime.min
            if force_invalid:
                cache.clear()

    @classmethod
    def ensure_worker_started(cls):
        """Start the eager fetching worker in the background."""
        if cls._eager_worker_task is None:
            try:
                loop = asyncio.get_running_loop()
                cls._eager_worker_task = loop.create_task(cls._eager_cache_worker())
                logger.info("DatastoreManager Eager Cache Background Worker started.")
            except RuntimeError:
                pass

    @classmethod
    async def _eager_cache_worker(cls):
        from src.config.loader import get_int_env
        from datetime import timedelta

        while True:
            try:
                await asyncio.sleep(60)

                expiry_minutes = get_int_env("CACHE_EXPIRY_MINUTES", 15)
                eager_limit = get_int_env("EAGER_CACHE_LIMIT", 5)

                ticker_metadata = GLOBAL_CONTEXT.get("ticker_metadata", {})
                cache = cls.get_history_cache()

                if not ticker_metadata or cls._fetch_callback is None:
                    continue

                sorted_by_heat = sorted(ticker_metadata.keys(), key=lambda sym: ticker_metadata[sym].get("heat", 0), reverse=True)
                top_eager = sorted_by_heat[:eager_limit]

                now = datetime.now()
                refresh_threshold = timedelta(minutes=expiry_minutes * 0.8)

                for sym in top_eager:
                    if sym.startswith(("HIGH_", "MOD_", "INACT_")):
                        continue

                    for cache_key, entry in list(cache.items()):
                        if cache_key.startswith(f"{sym}_"):
                            last_up = entry.get("last_updated")
                            if last_up and (now - last_up) >= refresh_threshold:
                                logger.info(f"[CACHE_SYNC] Eager background refresh triggered for hot ticker {sym}")
                                p = entry["period"]
                                i = entry["interval"]
                                try:
                                    # Use the registered callback to fetch data
                                    full_df = await asyncio.to_thread(cls._fetch_callback, [sym], p, i)
                                    ticker_df = full_df.dropna()
                                    if not ticker_df.empty:
                                        last_row = ticker_df.iloc[-1]
                                        data_str = f"### {sym}\n- **Period**: {p} | **Interval**: {i}\n- **Close**: {float(last_row['Close']):.2f}\n- **High**: {float(last_row['High']):.2f}\n- **Low**: {float(last_row['Low']):.2f}\n- **Volume**: {int(last_row['Volume']):,}\n"
                                        entry["data"] = data_str
                                        entry["last_updated"] = datetime.now()
                                except Exception as e:
                                    logger.error(f"[CACHE_SYNC] Eager fetch failed for {sym}: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"DatastoreManager Eager worker error: {e}")
