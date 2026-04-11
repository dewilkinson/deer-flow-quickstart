import asyncio
import pytest
from datetime import datetime, timedelta
from src.services.datastore import DatastoreManager
from src.tools.news import _analyze_news_impact, _resolve_contradictions

@pytest.mark.asyncio
async def test_news_narrative_flow():
    """ 
    Simulates a 3-month flow of news with classifications and contradictions.
    This test verifies that the 'Truth Window' remains consistent.
    """
    ticker = "MOCK"
    DatastoreManager.invalidate_cache(ticker)
    
    # 1. Day 1: Positive Outlook (DAILY)
    day1_news = "## News: MOCK\n- **MOCK reports Bullish growth in Q1** (Reuters)"
    impact1 = await _analyze_news_impact(ticker, ["MOCK reports Bullish growth in Q1"])
    assert impact1["impact"] == "DAILY"
    
    DatastoreManager.store_artifact(ticker, "news", "latest", day1_news, ttl=impact1["ttl_sec"])
    
    # Verify storage
    cached = DatastoreManager.get_artifact(ticker, "news", "latest")
    assert "Bullish" in cached["data"]

    # 2. Day 15: Structural Change (STRUCTURAL)
    day15_news = "## News: MOCK\n- **MOCK considering Acquisition of competitor** (Bloomberg)"
    impact15 = await _analyze_news_impact(ticker, ["MOCK considering Acquisition of competitor"])
    assert impact15["impact"] == "STRUCTURAL"
    
    # We don't overwrite the 'latest' cache in this specific test step, 
    # but we verify the resolution logic
    resolved_news = await _resolve_contradictions(ticker, day15_news)
    # No conflict yet
    assert "SUPERSEDENCE" not in resolved_news
    
    DatastoreManager.store_artifact(ticker, "news", "latest", resolved_news, ttl=impact15["ttl_sec"])

    # 3. Day 29: Positive Growth Re-affirmed (DAILY)
    day29_news = "## News: MOCK\n- **MOCK analysts reaffirm Bullish Growth outlook** (WSJ)"
    DatastoreManager.store_artifact(ticker, "news", "latest", day29_news, ttl=86400)

    # 4. Day 30: Contradiction! (DAILY)
    # We now report Contraction, which conflicts with Day 29's Growth
    day30_news = "## News: MOCK\n- **MOCK reports unexpected Contraction in revenues** (WSJ)"
    impact30 = await _analyze_news_impact(ticker, ["MOCK reports unexpected Contraction in revenues"])
    
    resolved_day30 = await _resolve_contradictions(ticker, day30_news)
    
    # Verify that the contradiction was detected
    assert "SUPERSEDENCE DETECTED" in resolved_day30
    assert "conflicts with prior GROWTH outlook" in resolved_day30
    
    DatastoreManager.store_artifact(ticker, "news", "latest", resolved_day30, ttl=impact30["ttl_sec"])

    # 4. FLASH Event (FLASH)
    flash_news = "## FLASH: MOCK\n- **BREAKING: MOCK trading HALTED pending announcement**"
    impact_flash = await _analyze_news_impact(ticker, ["BREAKING: MOCK trading HALTED pending announcement"])
    assert impact_flash["impact"] == "FLASH"
    assert impact_flash["ttl_sec"] == 60
    
    DatastoreManager.store_artifact(ticker, "news", "latest", flash_news, ttl=impact_flash["ttl_sec"])
    
    # Verify FLASH is presence
    flash_check = DatastoreManager.get_artifact(ticker, "news", "latest")
    assert "HALTED" in flash_check["data"]

if __name__ == "__main__":
    asyncio.run(test_news_narrative_flow())
