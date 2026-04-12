import logging
import asyncio
from typing import Any
from datetime import datetime
from langchain_core.tools import tool
import yfinance
from src.services.datastore import DatastoreManager

logger = logging.getLogger(__name__)

@tool
async def get_ticker_news(ticker: str) -> str:
    """
    Scout Primitive: Fetches and categorizes the latest news for a specific ticker.
    Implements Narrative Caching with contradiction resolution.
    """
    t = ticker.upper()
    
    # 1. Cache lookup
    cached = DatastoreManager.get_artifact(t, "news", "latest")
    if cached:
        logger.info(f"[NEWS] Cache hit for {t}")
        return cached.get("data", "")

    # 2. Fetch from YFinance
    try:
        ticker_obj = yfinance.Ticker(t)
        news_items = ticker_obj.news[:5] # Get top 5
        
        if not news_items:
            return f"No recent news found for {t}."

        report = [f"## Latest News: {t}", ""]
        headlines = []
        
        for item in news_items:
            title = item.get("title", "")
            publisher = item.get("publisher", "Unknown")
            link = item.get("link", "#")
            headlines.append(title)
            report.append(f"- **{title}** ({publisher})")
            report.append(f"  [Read More]({link})")

        full_report = "\n".join([str(r) for r in report])
        
        # 3. Categorization & Contradiction Resolution (Phase 5 Logic)
        impact_data = await _analyze_news_impact(t, headlines)
        
        # 4. Resolve Contradictions
        final_report = await _resolve_contradictions(t, full_report)
        
        # 4. Store in Hybrid Cache with dynamic TTL
        DatastoreManager.store_artifact(
            t, "news", "latest", final_report, 
            ttl=impact_data.get("ttl_sec", 3600),
            persist=True
        )
        
        return final_report
    except Exception as e:
        logger.error(f"News fetch failed for {t}: {e}")
        return f"[ERROR]: Failed to fetch news for {t}: {e}"

async def _analyze_news_impact(ticker: str, headlines: list[str]) -> dict[str, Any]:
    """ 
    Categorizes news into impact levels for dynamic TTL.
    FLASH (60s), DAILY (24h), STRUCTURAL (30d)
    """
    text = " ".join([str(h) for h in headlines]).upper()
    
    # Priority 1: FLASH (Immediate volatility)
    if any(k in text for k in ["BREAKING", "FLASH", "HALTED", "SPIKE", "CRASH"]):
        return {"impact": "FLASH", "ttl_sec": 60}
        
    # Priority 2: STRUCTURAL (Long-term shifts)
    if any(k in text for k in ["ACQUISITION", "MERGER", "CEO", "BANKRUPTCY", "REGULATORY"]):
        return {"impact": "STRUCTURAL", "ttl_sec": 2592000} # 30 days
        
    # Default: DAILY
    return {"impact": "DAILY", "ttl_sec": 86400}

async def _resolve_contradictions(ticker: str, new_report: str) -> str:
    """ Checks for conflicting reports and marks them as SUPERSEDED. """
    # Get previous report from RAM
    old_report_obj = DatastoreManager.get_artifact(ticker, "news", "latest")
    if not old_report_obj:
        return new_report
        
    old_report = old_report_obj.get("data", "")
    if not old_report:
        return new_report
        
    # Simple semantic conflict detection (Placeholder for full LLM logic)
    conflicts = [
        ("BULLISH", "BEARISH"),
        ("GROWTH", "CONTRACTION"),
        ("ACQUIRED", "DENIED"),
        ("EXPANSION", "REDUCTION")
    ]
    
    resolved_report = new_report
    new_upper = new_report.upper()
    old_upper = old_report.upper()
    
    for term1, term2 in conflicts:
        # Check both directions
        if (term1 in new_upper and term2 in old_upper) or (term2 in new_upper and term1 in old_upper):
            conflict_term = term2 if term1 in new_upper else term1
            resolved_report = f"> [!WARNING]\n> **SUPERSEDENCE DETECTED**: New data conflicts with prior {conflict_term} outlook.\n\n" + resolved_report
            break
            
    return resolved_report
