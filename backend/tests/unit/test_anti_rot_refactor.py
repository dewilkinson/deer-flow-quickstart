import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.graph.nodes.reporter import reporter_node
from langchain_core.runnables import RunnableConfig

@pytest.mark.asyncio
async def test_stateless_transaction_truncation():
    """Test that the reporter correctly squashes messages into 1 turn."""
    
    # 10 historical human messages
    mock_messages = [HumanMessage(content=f"Msg {i}") for i in range(10)]
    
    state = {
        "messages": mock_messages,
        "final_report": None
    }
    
    config = RunnableConfig()

    with patch('src.graph.nodes.reporter.get_llm_by_type') as mock_get_llm, \
         patch('src.graph.nodes.reporter.apply_prompt_template') as mock_apply:
         
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Mocked Synthesis"))
        mock_get_llm.return_value = mock_llm
        
        mock_apply.return_value = "Mocked Prompt"
        
        await reporter_node(state, config)
        
        # apply_prompt_template("reporter", state, ...)
        # args[0] is "reporter", args[1] is state
        state_passed = mock_apply.call_args[0][1]
        
        # VLI refactor squashes history into 1 message
        assert len(state_passed["messages"]) == 1
        # Ensure it contains the last message at the end
        assert "Msg 9" in state_passed["messages"][0].content
        # And ensure the start Message 0 is there (since we squashed all 10 into 1, 
        # but reporter has MAX_HISTORY=12 so all 10 should be there)
        assert "Msg 0" in state_passed["messages"][0].content


@pytest.mark.asyncio
async def test_data_compression_routine():
    """Test that the reporter dynamically flattens massive JSON arrays returning from Tools."""
    
    # 1 massive JSON array with 600 items (Threshold is 500)
    huge_json_list = json.dumps([{"id": i, "val": "huge"} for i in range(600)])
    mock_messages = [ToolMessage(content=huge_json_list, name="smc_analyst", tool_call_id="123")]
    
    state = {
        "messages": mock_messages,
        "final_report": None
    }
    config = RunnableConfig()

    with patch('src.graph.nodes.reporter.get_llm_by_type') as mock_get_llm, \
         patch('src.graph.nodes.reporter.apply_prompt_template') as mock_apply:
         
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Mocked Synthesis"))
        mock_get_llm.return_value = mock_llm
        
        mock_apply.return_value = "Mocked Prompt"
        
        await reporter_node(state, config)
        
        state_passed = mock_apply.call_args[0][1]
        
        compressed_content = state_passed["messages"][0].content
        # It should no longer contain raw json of index 599
        assert "599" not in compressed_content
        # It should contain the compressed mathematical summary instead
        assert "Truncated JSON List of 600 items" in compressed_content


def test_router_logic_bypass():
    """Test that the structural builder correctly intercepts final reports to bypass reporter overhead."""
    from src.graph.builder import router_logic
    from langgraph.graph import END

    # Case 1: Fast-Path complete.
    state_short = {"final_report": "Direct result.", "raw_data_mode": True}
    assert router_logic(state_short) == END

    # Case 2: Full pipeline required.
    state_full = {"final_report": None, "raw_data_mode": False}
    assert router_logic(state_full) == "reporter"
