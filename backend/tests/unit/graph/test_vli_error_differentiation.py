import pytest
import time
from unittest.mock import AsyncMock, patch
from langchain_core.messages import AIMessage, HumanMessage
from src.graph.nodes.common_vli import _run_node_with_tiered_fallback

@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_quota_exhausted_classification():
    """Verify that a 429/Resource Exhausted error is classified as QUOTA_EXHAUSTED."""
    # Mock the LLM to raise a Resource Exhausted exception
    mock_llm = AsyncMock()
    # We mock it to fail on the reasoning tier
    mock_llm.ainvoke.side_effect = Exception("429: Resource has been exhausted (QUOTA_EXHAUSTED)")

    # Standard patching after common_vli refactor
    with patch("src.graph.nodes.common_vli.get_llm_by_type", return_value=mock_llm), \
         patch("src.graph.nodes.common_vli.create_agent_from_registry", return_value=mock_llm):
        
        state = {"messages": []}
        messages = [HumanMessage(content="User prompt")]
        config = {"configurable": {"execution_start_time": time.time()}}
        
        # We expect it to try all 3 tiers and then return the final error
        result, fallback_messages = await _run_node_with_tiered_fallback("coordinator", state, config, messages=messages)
        
        # Check either result.content (AIMessage) or result['thought'] (Structured dict)
        content = result.content if hasattr(result, "content") else str(result)
        assert "QUOTA_EXHAUSTED" in content
        assert "system_fallback_error" in getattr(result, "name", "") or "system_fallback_error" in str(result)

@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_structural_exception_classification():
    """Verify that an instruction leak is classified as STRUCTURAL_EXCEPTION."""
    # Mock the LLM to return a message containing a leak keyword
    mock_llm = AsyncMock()
    # First tier: Return a leak
    # Second tier: Return a clean message
    mock_llm.ainvoke.side_effect = [
        AIMessage(content="INTERNAL_DATA: # SECURITY OVERRIDE detected."),
        AIMessage(content="Clean response.")
    ]

    # Standard patching after common_vli refactor
    with patch("src.graph.nodes.common_vli.get_llm_by_type", return_value=mock_llm), \
         patch("src.graph.nodes.common_vli.create_agent_from_registry", return_value=mock_llm):
        
        state = {"messages": []}
        messages = [HumanMessage(content="User prompt")]
        config = {"configurable": {"execution_start_time": time.time()}}
        
        result, fallback_messages = await _run_node_with_tiered_fallback("coordinator", state, config, messages=messages)
        
        # Should have one fallback message about Structural Exception
        assert any("STRUCTURAL_EXCEPTION" in str(m.content) for m in fallback_messages)
        assert result.content == "Clean response."
