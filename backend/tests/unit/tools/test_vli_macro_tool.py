import asyncio
import pytest
import os
import json
from src.tools.finance import get_macro_stocks

@pytest.mark.asyncio
async def test_get_macro_stocks_execution():
    """Verifies that the macro tool executes, fetches data, and saves the artifact."""
    # 1. Run the tool
    result = await get_macro_stocks.ainvoke({})
    
    # 2. Check result content
    assert "# Macro Stocks State" in result
    assert "| SPY |" in result
    assert "| BTC |" in result
    
    # 3. Check artifact generation
    artifact_path = os.path.join("data", "artifacts", "get_macro_stocks.json")
    assert os.path.exists(artifact_path)
    
    with open(artifact_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert "SPY" in data
        assert "BTC" in data
        assert "price" in data["SPY"]
        assert "change_pct" in data["SPY"]

if __name__ == "__main__":
    asyncio.run(test_get_macro_stocks_execution())
