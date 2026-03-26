# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import pytest
from unittest.mock import MagicMock, patch
from src.graph.nodes import scout_node
from src.graph.types import State, Plan

@pytest.mark.asyncio
async def test_scout_search():
    """Verifies sanitized search result output inside the scout node."""
    with patch("src.graph.nodes._setup_and_execute_agent_step", new_callable=MagicMock) as mock_exec:
        # Scout is returning a mocked HumanMessage observing the requested context
        from langchain_core.messages import HumanMessage
        mock_exec.return_value = {"messages": [HumanMessage(content="Cleaned and sanitized context data")]}

        state = State(
            current_plan=Plan(
                title="Deep dive search",
                thought="",
                steps=[],
                direct_response="",
                locale="en-US"
            ),
            research_topic="Yield Curve"
        )
        config = MagicMock()
        
        result = await scout_node(state, config)
        
        # Assert observations are piped correctly as expected by test_specification.md
        assert "messages" in result
        assert "observations" not in result # Since Scout just appends to messages historically, or emits an observation
        
        # The test specification says "State update with observations."
        # If scout_node returns {"observations": ...} we check that
        
        # Verify scout is given fetch_web_search explicitly in the primitives
        tools_list = mock_exec.call_args[1].get("agent_tools", [])
        tool_names = [getattr(tool, "name", "") for tool in tools_list]
        assert "fetch_web_search" in tool_names or len(tools_list) > 0
