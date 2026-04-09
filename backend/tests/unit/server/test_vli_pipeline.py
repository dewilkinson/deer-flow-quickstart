from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from src.server.app import _invoke_vli_agent


@pytest.mark.asyncio
async def test_invoke_vli_agent_smc_pipeline():
    """
    E2E Integration test for the _invoke_vli_agent pipeline.
    Mocking graph and DB to ensure it completes in unit test environment.
    """
    pipeline_request = "run smc analysis on ETHUSDT"

    with patch('src.server.app.graph') as mock_graph, \
         patch('src.server.app.research_db') as mock_db:
         
        # Mock graph results
        mock_graph.ainvoke = AsyncMock(return_value={
            "final_report": "Mocked SMC Report content"
        })
        
        # Mock DB results
        mock_db.create_research_project.return_value = MagicMock(id="p1")
        mock_db.create_research_session.return_value = MagicMock(id="s1")

        # _invoke_vli_agent returns (final_report, state)
        response_text, _ = await _invoke_vli_agent(pipeline_request, direct_mode=False)

        # Verify pipeline output format
        assert isinstance(response_text, str)
        assert "Mocked SMC Report content" in response_text
        assert len(response_text) > 10
