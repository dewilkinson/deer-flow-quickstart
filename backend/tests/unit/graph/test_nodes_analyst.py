# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import pytest
from unittest.mock import MagicMock, patch
from src.graph.nodes import analyst_node
from langchain_core.messages import HumanMessage
from src.graph.types import State, Plan

@pytest.mark.asyncio
async def test_analyst_node_verbosity_zero():
    """Test that the analyst node correctly implements verbosity controls."""
    with patch("src.graph.nodes._setup_and_execute_agent_step", new_callable=MagicMock) as mock_exec:
        mock_exec.return_value = {"messages": [HumanMessage(content="Result without filler")]}

        state = State(
            current_plan=Plan(
                title="Financial modeling",
                thought="Focus heavily on quantitative metrics.",
                steps=[],
                direct_response="",
                locale="en-US"
            ),
            research_topic="Test Topic",
            verbosity=0
        )
        
        config = MagicMock()
        result = await analyst_node(state, config)
        
        # Verify result structure output matches expected
        assert "messages" in result
        
        # Verify _setup_and_execute_agent_step was called, verify kwargs
        mock_exec.assert_called_once()
        kwargs = mock_exec.call_args[1]
        assert "verbosity=0" in kwargs.get("agent_instructions", "")

@pytest.mark.asyncio
async def test_analyst_restriction():
    """Ensure analyst uses the correct set of tools and restrictions are respected."""
    with patch("src.graph.nodes._setup_and_execute_agent_step", new_callable=MagicMock) as mock_exec:
        state = State(
            current_plan=Plan(
                title="Analysis",
                thought="",
                steps=[],
                direct_response="",
                locale="en-US"
            ),
            verbosity=1
        )
        config = MagicMock()
        await analyst_node(state, config)
        
        # Pull tools list
        tools_list = mock_exec.call_args[1].get("agent_tools", [])
        tool_names = [getattr(tool, "name", "") for tool in tools_list]
        
        # We explicitly ensure yfinance is NOT in the tools list 
        # (This implements the user's specific workflow requirement)
        assert "yfinance" not in tool_names
        
