import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

@tool
def invalidate_market_cache(ticker: str = "") -> str:
    """
    Invalidate the market data cache for a specific ticker (e.g. 'AAPL') or the entire cache if no ticker is provided.
    This is useful if you suspect data is stale or if price drift is detected.
    """
    from src.services.datastore import DatastoreManager
    return DatastoreManager.invalidate_cache(ticker)

@tool
def simulate_cache_volatility(force_invalid: bool = False) -> str:
    """
    Diagnostic tool to simulate price volatility and test cache consistency logic.
    """
    from src.services.datastore import DatastoreManager
    return DatastoreManager.simulate_volatility(force_invalid)
