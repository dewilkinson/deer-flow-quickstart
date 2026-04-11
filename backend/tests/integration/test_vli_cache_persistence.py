import pytest
import time
from src.services.datastore import DatastoreManager
from src.config.database import PersistentCache, get_session_local

@pytest.fixture(autouse=True)
def clean_system():
    DatastoreManager.invalidate_cache()
    yield
    DatastoreManager.invalidate_cache()

@pytest.mark.asyncio
async def test_write_through_persistence():
    """Verify that storing an artifact writes to PostgreSQL."""
    ticker = "TSLA"
    resource = "smc_analysis" # Always persisted
    tf = "1h"
    data = {"score": 0.85, "bias": "Bullish"}
    price = 180.0
    
    # Store with persist=True (default)
    DatastoreManager.store_artifact(ticker, resource, tf, data, price=price)
    
    # Check DB directly
    SessionLocal = get_session_local()
    with SessionLocal() as db:
        record = db.query(PersistentCache).filter(
            PersistentCache.ticker == ticker,
            PersistentCache.resource_type == resource
        ).first()
        
        assert record is not None
        assert record.reference_price == price
        # Record data is a string/json
        import json
        assert json.loads(record.data)["score"] == 0.85

@pytest.mark.asyncio
async def test_read_through_persistence():
    """Verify that a RAM-miss triggers a DB read and promotion to RAM."""
    ticker = "NVDA"
    resource = "smc_analysis"
    tf = "4h"
    data = "Complex Analysis Report"
    price = 900.0
    
    # 1. Store and persist
    DatastoreManager.store_artifact(ticker, resource, tf, data, price=price)
    
    # 2. Flush RAM ONLY (Atomic clear clears both, so we manually wipe history_cache)
    from src.tools.shared_storage import analysis_cache
    analysis_cache.clear()
    assert ticker not in analysis_cache
    
    # 3. Request artifact (Should trigger Read-Through)
    artifact = DatastoreManager.get_artifact(ticker, resource, tf)
    
    assert artifact["data"] == data
    # Verify it was promoted back to RAM
    assert ticker in analysis_cache
    assert analysis_cache[ticker]["timeframes"][tf]["data"] == data

@pytest.mark.asyncio
async def test_cache_expiration():
    """Verify that expired DB records are deleted and not returned."""
    ticker = "EXPIRED_TEST"
    resource = "history"
    tf = "1m"
    
    # Manually inject an expired record into DB
    from datetime import datetime, timedelta
    SessionLocal = get_session_local()
    with SessionLocal() as db:
        new_entry = PersistentCache(
            ticker=ticker,
            resource_type=resource,
            timeframe=tf,
            reference_price=10.0,
            data="Old Data",
            expires_at=datetime.utcnow() - timedelta(hours=1), # Expired 1h ago
            created_at=datetime.utcnow() - timedelta(hours=2)
        )
        db.add(new_entry)
        db.commit()
        
    # Request artifact
    artifact = DatastoreManager.get_artifact(ticker, resource, tf)
    assert artifact == {}
    
    # Verify it was deleted from DB
    with SessionLocal() as db:
        record = db.query(PersistentCache).filter(PersistentCache.ticker == ticker).first()
        assert record is None
