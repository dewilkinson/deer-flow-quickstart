# Tests for the Portfolio Manager Agent Node
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from langchain_core.messages import HumanMessage
from src.graph.nodes.portfolio_manager import portfolio_manager_node
from src.graph.types import State, Plan

@pytest.mark.asyncio
async def test_portfolio_manager_node_initialization():
    # Verify node is callable
    assert callable(portfolio_manager_node)

@pytest.mark.asyncio
async def test_portfolio_manager_node_execution():
    """Test that the Portfolio Manager node correctly executes with its strategic toolset."""
    with patch("src.graph.nodes.portfolio_manager._setup_and_execute_agent_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {"messages": [HumanMessage(content="Portfolio analysis complete. Added NVDA to Watchlist.")]}

        state = State(
            current_plan=Plan(
                title="Portfolio Oversight",
                thought="",
                steps=[],
                direct_response="",
                locale="en-US",
                has_enough_context=False
            ),
            research_topic="Strategic Review",
            verbosity=1
        )
        
        config = MagicMock()
        result = await portfolio_manager_node(state, config)
        
        # Verify result structure output matches expected
        assert "messages" in result
        
        # Verify _setup_and_execute_agent_step was called, verify tools
        mock_exec.assert_called_once()
        args, kwargs = mock_exec.call_args
        
        # Check that specific portfolio tools are present in the tools payload
        tools = args[3]
        tool_names = [getattr(t, 'name', getattr(t, '__name__', str(t))) for t in tools]
        assert "update_watchlist" in tool_names
        assert "get_portfolio_balance_report" in tool_names
        assert "get_smc_analysis" in tool_names
        assert "fetch_market_macros" in tool_names
        
        # Verify specific instructions regarding War Barbell were passed
        assert "War Barbell" in kwargs.get("agent_instructions", "")
