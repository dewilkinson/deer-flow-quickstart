# Heat Manager for VLI Symbol Prioritization
# Cobalt Multiagent - High-fidelity financial analysis platform

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class HeatManager:
    """ Manages symbol 'Heat' scores to protect frequently used assets from cache eviction. """
    
    _symbol_heat: Dict[str, float] = {}
    _decay_task: asyncio.Task = None
    _is_running: bool = False

    @classmethod
    def increment_heat(cls, ticker: str, amount: float = 1.0):
        """ Adds heat to a symbol, typically on access or analysis. """
        ticker = ticker.upper()
        cls._symbol_heat[ticker] = cls._symbol_heat.get(ticker, 0.0) + amount
        logger.debug(f"[HEAT] {ticker} heat incremented to {cls._symbol_heat[ticker]:.2f}")

    @classmethod
    def get_heat_score(cls, ticker: str) -> float:
        """ Returns the current heat score for a symbol. """
        return cls._symbol_heat.get(ticker.upper(), 0.0)

    @classmethod
    def get_protected_symbols(cls, top_n: int = 20) -> List[str]:
        """ Returns the symbols with the highest heat scores (Immune Tier). """
        sorted_symbols = sorted(cls._symbol_heat.items(), key=lambda x: x[1], reverse=True)
        return [ticker for ticker, score in sorted_symbols[:top_n] if score > 0]

    @classmethod
    def get_heat_map(cls) -> Dict[str, float]:
        """ Returns a copy of the current heat map. """
        return cls._symbol_heat.copy()

    @classmethod
    def clear_heat(cls, ticker: str = None):
        """ Clears heat score for a specific ticker, or all tickers if none provided. """
        if ticker:
            t = ticker.upper()
            if t in cls._symbol_heat:
                del cls._symbol_heat[t]
                logger.debug(f"[HEAT] {t} heat cleared.")
        else:
            cls._symbol_heat.clear()
            logger.info("[HEAT_MANAGER] All heat scores have been cleared.")

    @classmethod
    async def start_decay_worker(cls, interval_hours: int = 1):
        """ Starts the background task that decays heat scores hourly. """
        if cls._is_running:
            return
            
        cls._is_running = True
        cls._decay_task = asyncio.create_task(cls._decay_loop(interval_hours))
        logger.info(f"[HEAT_MANAGER] Started heat decay worker (Interval: {interval_hours}h)")

    @classmethod
    async def _decay_loop(cls, hours: int):
        """ Background loop that applies decay logic. """
        while cls._is_running:
            try:
                # Wait for the next interval
                await asyncio.sleep(hours * 3600)
                cls._perform_decay()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[HEAT_MANAGER] Error in decay loop: {e}")
                await asyncio.sleep(60) # Backoff

    @classmethod
    def _perform_decay(cls, override_pct: float = None):
        """ Reduces all heat scores by the configured decay percentage. """
        from src.config.loader import get_config
        
        config = get_config()
        if override_pct is not None:
            decay_pct = override_pct / 100.0
        else:
            decay_pct = config.get("CACHE_POLICIES", {}).get("default", {}).get("heat_decay_pct", 10.0) / 100.0
        
        logger.info(f"[HEAT_MANAGER] Applying {decay_pct*100}% hourly decay across {len(cls._symbol_heat)} symbols")
        
        # Iterate and apply decay
        to_delete = []
        for ticker in cls._symbol_heat:
            cls._symbol_heat[ticker] *= (1.0 - decay_pct)
            
            # If heat is negligible, mark for cleanup to prevent memory bloat
            if cls._symbol_heat[ticker] < 0.01:
                to_delete.append(ticker)
        
        for ticker in to_delete:
            del cls._symbol_heat[ticker]
            logger.debug(f"[HEAT] {ticker} recycled due to negligible heat.")

    @classmethod
    def stop_decay_worker(cls):
        """ Stops the background decay process. """
        cls._is_running = False
        if cls._decay_task:
            cls._decay_task.cancel()
            logger.info("[HEAT_MANAGER] Heat decay worker stopped.")
