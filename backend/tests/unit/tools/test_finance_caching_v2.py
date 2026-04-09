from datetime import datetime, timedelta
import pytest
from unittest.mock import MagicMock

# Import the actual global context used by the tools
from src.tools.shared_storage import GLOBAL_CONTEXT
from src.tools.finance import get_cache_heat_map, get_symbol_history_data, simulate_cache_volatility

@pytest.fixture(autouse=True)
def setup_isolation():
    """Ensure a fresh global context for each test."""
    GLOBAL_CONTEXT.clear()
    yield
    GLOBAL_CONTEXT.clear()


@pytest.mark.asyncio
async def test_system_cache_seeding_and_weighting():
    """
    Simulates the VLI Dashboard's diagnostic flow:
    1. Seed 50 mock stocks via System Node tool.
    2. Verify weighting/heat distribution.
    3. Verify Heat Map generation.
    """
    # 1. Seed the cache
    result = await simulate_cache_volatility.ainvoke({"num_high": 10, "num_moderate": 30, "num_inactive": 10})
    assert "Successfully populated 50 mock stocks" in result

    ticker_metadata = GLOBAL_CONTEXT.get("ticker_metadata", {})
    
    # 2. Verify total population
    assert len(ticker_metadata) == 50

    # 3. Verify weighting (Heat)
    high_heat_stocks = [s for s in ticker_metadata if s.startswith("HIGH_")]
    mod_heat_stocks = [s for s in ticker_metadata if s.startswith("MOD_")]
    inact_stocks = [s for s in ticker_metadata if s.startswith("INACT_")]

    assert all(ticker_metadata[s]["heat"] >= 25 for s in high_heat_stocks)
    assert all(8 <= ticker_metadata[s]["heat"] <= 18 for s in mod_heat_stocks)
    assert all(ticker_metadata[s]["heat"] <= 3 for s in inact_stocks)

    # 4. Verify Heat Map output
    heat_map = await get_cache_heat_map.ainvoke({})
    assert "VLI Hybrid Cache Heat Map" in heat_map
    assert "HIGH_0" in heat_map
    assert "INACT_0" in heat_map
