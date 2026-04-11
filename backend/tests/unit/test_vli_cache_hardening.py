import pytest
import time
from datetime import datetime, timedelta
from src.services.datastore import DatastoreManager
from src.services.heat_manager import HeatManager
from src.tools.shared_storage import history_cache

@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure caches are clear before and after each test."""
    DatastoreManager.invalidate_cache()
    HeatManager._symbol_heat.clear()
    yield
    DatastoreManager.invalidate_cache()
    HeatManager._symbol_heat.clear()

def test_lru_eviction_limit():
    """Verify that the cache respects the 1,000 symbol limit (or configured limit)."""
    # Force a small limit for testing
    from src.config.loader import load_yaml_config
    
    # We'll simulate 105 tickers with a 100 limit (logic should evict 5)
    # Using 'store_artifact' which triggers '_enforce_capacity'
    
    # Note: For testing we might want to monkeypatch the limit
    for i in range(1050): # Go over the default 1000 limit
        ticker = f"TICKER_{i}"
        DatastoreManager.store_artifact(ticker, "history", "1h", f"Data {i}", price=100.0, persist=False)
    
    # Check if history_cache size is capped at 1000
    assert len(history_cache) == 1000
    
    # TICKER_20 should be gone (TICKER_0-19 are protected by Heat Manager Top 20)
    assert "TICKER_20" not in history_cache
    # TICKER_1049 should be present
    assert "TICKER_1049" in history_cache

def test_heat_immunity():
    """Verify that Top 20 hot symbols are protected from LRU eviction."""
    # 1. Fill cache to near limit (990 items)
    for i in range(990):
        DatastoreManager.store_artifact(f"OLD_{i}", "history", "1h", "data", price=100.0, persist=False)
    
    # 2. Make one ticker VERY hot
    hot_ticker = "HOT_SYMBOL"
    HeatManager.increment_heat(hot_ticker, 5000)
    DatastoreManager.store_artifact(hot_ticker, "history", "1h", "data", price=100.0, persist=False)
    
    # 3. Add 50 more items to force eviction of 41 items
    # The 'HOT_SYMBOL' is the oldest among some items, but it should be protected
    for i in range(50):
        DatastoreManager.store_artifact(f"NEW_{i}", "history", "1h", "data", price=100.0, persist=False)
        
    assert hot_ticker in history_cache
    assert len(history_cache) == 1000

def test_price_drift_invalidation():
    """Verify that >1% drift triggers an atomic purge of the symbol container."""
    ticker = "AAPL"
    # Initial store
    DatastoreManager.store_artifact(ticker, "history", "1h", "Initial Data", price=150.0, persist=False)
    DatastoreManager.store_artifact(ticker, "analysis", "1h", "Initial Analysis", price=150.0, persist=False)
    
    assert ticker in history_cache
    
    # Update with <1% drift (0.5%) - Should NOT purge
    DatastoreManager.store_artifact(ticker, "history", "1h", "Secondary Data", price=150.75, persist=False)
    assert ticker in history_cache
    
    # Update with >1% drift (2%) - Should trigger Atomic Purge
    DatastoreManager.store_artifact(ticker, "history", "1h", "Drifted Data", price=153.50, persist=False)
    
    # Symbol should be gone from ALL caches
    assert ticker not in history_cache
    from src.tools.shared_storage import analysis_cache
    assert ticker not in analysis_cache

def test_heat_decay():
    """Verify 10% hourly heat decay."""
    ticker = "BTC"
    HeatManager.increment_heat(ticker, 100)
    assert HeatManager.get_heat_score(ticker) == 100
    
    # Manually trigger decay
    HeatManager._perform_decay(override_pct=10.0)
    assert HeatManager.get_heat_score(ticker) == 90.0
    
    HeatManager._perform_decay(override_pct=10.0)
    assert HeatManager.get_heat_score(ticker) == 81.0
