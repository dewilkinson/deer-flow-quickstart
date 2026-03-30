import pytest
import asyncio
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from src.graph.nodes.terminal_specialist import terminal_specialist_node
from src.graph.nodes.vision_specialist import vision_specialist_node
from src.graph.types import State

@pytest.mark.asyncio
async def test_terminal_specialist_interrupt():
    """Verify that Terminal Specialist triggers an interrupt for sensitive commands."""
    state = {
        "messages": [HumanMessage(content="Terminal, delete the test file.", name="user")],
        "is_test_mode": True,
        "steps_completed": 0,
        "current_plan": "test plan"
    }
    config = {"configurable": {"thread_id": "test_thread"}}

    # Mock the tool to return APPROVAL_REQUIRED
    with patch("src.graph.nodes.terminal_specialist._setup_and_execute_agent_step") as mock_exec:
        mock_exec.return_value = {
            "messages": [AIMessage(content='{"status": "APPROVAL_REQUIRED", "command": "rm test.txt", "reason": "Sensitive operation"}', name="terminal_specialist")]
        }
        
        # We expect a langgraph interrupt to be raised
        with patch("src.graph.nodes.terminal_specialist.interrupt") as mock_interrupt:
            mock_interrupt.return_value = "[ACCEPTED]"
            
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="Deleted", stderr="", returncode=0)
                
                result = await terminal_specialist_node(state, config)
                
                # Verify interrupt was called
                mock_interrupt.assert_called_once()
                # Verify final message shows execution after approval
                assert "User approved. Executed `rm test.txt`" in result["messages"][-1].content

@pytest.mark.asyncio
async def test_vision_specialist_purge():
    """Verify that Vision Specialist purges raw image data after extraction."""
    multimodal_content = [
        {"type": "text", "text": "Analyze this chart."},
        {"type": "image_url", "image_url": "data:image/png;base64,IMAGEDATA..."}
    ]
    state = {
        "messages": [HumanMessage(content=multimodal_content, name="user")],
        "is_test_mode": True,
        "steps_completed": 0,
        "current_plan": "test plan"
    }
    config = {"configurable": {"thread_id": "test_thread"}}

    with patch("src.graph.nodes.vision_specialist._setup_and_execute_agent_step") as mock_exec:
        mock_exec.return_value = {
            "messages": [AIMessage(content="Analysis: Bullish", name="vision_specialist")]
        }
        
        result = await vision_specialist_node(state, config)
        
        # Verify HumanMessage content is now clean text, not a list of images
        msg = result["messages"][0]
        assert isinstance(msg.content, str)
        assert "Analyze this chart." in msg.content
        assert "base64" not in msg.content
