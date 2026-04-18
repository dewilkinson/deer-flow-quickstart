import os
import pytest
import asyncio
import time
from unittest.mock import MagicMock

# Force stateless mode to avoid DB overhead during standalone tests
os.environ["VLI_CACHE_DISABLED"] = "True"
os.environ["VLI_MEMORY_MODE"] = "True"

from src.tools.finance import get_stock_quote

@pytest.mark.asyncio
async def test_quote_aapl_fast_path():
    """Verify successful retrieval of a standard equity ticker via Fast-Path."""
    start = time.time()
    result = await get_stock_quote.ainvoke({"ticker": "AAPL", "use_fast_path": True})
    latency = time.time() - start
    
    assert isinstance(result, dict)
    assert result["symbol"] == "AAPL"
    assert "price" in result
    assert result["price"] > 0
    print(f"\n[PASS] AAPL Fast-Path: ${result['price']} (Latency: {latency:.2f}s)")

@pytest.mark.asyncio
async def test_quote_btc_normalization():
    """Verify that BTC is correctly normalized to BTC-USD and fetched."""
    result = await get_stock_quote.ainvoke({"ticker": "BTC", "use_fast_path": True})
    
    assert isinstance(result, dict)
    assert result["symbol"] == "BTC-USD"
    assert "price" in result
    assert result["is_fast_fetch"] is True
    print(f"\n[PASS] BTC Normalization: ${result['price']}")

@pytest.mark.asyncio
async def test_quote_eth_normalization():
    """Verify that ETH is correctly normalized to ETH-USD and fetched."""
    result = await get_stock_quote.ainvoke({"ticker": "ETH", "use_fast_path": True})
    
    assert isinstance(result, dict)
    assert result["symbol"] == "ETH-USD"
    assert "price" in result
    print(f"\n[PASS] ETH Normalization: ${result['price']}")

@pytest.mark.asyncio
async def test_quote_invalid_ticker_handling():
    """Verify that an invalid ticker returns a clean error string instead of crashing."""
    ticker = "INVALID_TICKER_999_XYZ"
    result = await get_stock_quote.ainvoke({"ticker": ticker, "use_fast_path": True})
    
    # It should fall back to standard fetch, then error out
    assert isinstance(result, str)
    assert "[ERROR]" in result or "unavailable" in result
    print(f"\n[PASS] Invalid Ticker handled correctly: {result}")

@pytest.mark.asyncio
async def test_quote_standard_path_fallback():
    """Verify that disabling Fast-Path results in a successful history-based fetch."""
    start = time.time()
    result = await get_stock_quote.ainvoke({"ticker": "SPY", "use_fast_path": False})
    latency = time.time() - start
    
    assert isinstance(result, dict)
    assert result["symbol"] == "SPY"
    assert "price" in result
    assert not result.get("is_fast_fetch", False)
    print(f"\n[PASS] SPY Standard Path: ${result['price']} (Latency: {latency:.2f}s)")
