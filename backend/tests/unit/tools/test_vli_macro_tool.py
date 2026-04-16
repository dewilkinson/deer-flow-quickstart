import asyncio
import pytest
import os
import json
import pandas as pd
from unittest.mock import patch, MagicMock
from src.tools.finance import get_macro_symbols

@pytest.mark.asyncio
@patch("src.tools.finance._fetch_batch_history")
@patch("src.tools.finance._extract_ticker_data")
async def test_get_macro_stocks_execution(mock_extract, mock_fetch):
    """Verifies that the macro tool executes using mocked data."""
    # 1. Mock the batch fetch to return anything non-empty
    mock_fetch.return_value = pd.DataFrame({"dummy": [1, 2]})
    
    # 2. Mock the extractor to return a valid 2-row dataframe for any ticker
    def mock_extract_fn(df, ticker):
        return pd.DataFrame({
            "Close": [400.0, 410.0],
            "Volume": [1000, 1100]
        })
    mock_extract.side_effect = mock_extract_fn

    # 3. Run the tool
    result = await get_macro_symbols.ainvoke({})
    
    # 4. Check result content (New JSON format)
    assert '"type": "table"' in result
    assert '"Asset", "Ticker", "Price"' in result
    
    # 5. Check artifact generation
    artifact_path = os.path.join("data", "artifacts", "get_macro_symbols.json")
    if os.path.exists(artifact_path):
        with open(artifact_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Just verify the artifact is populated
            assert len(data) > 0

if __name__ == "__main__":
    asyncio.run(test_get_macro_stocks_execution())
