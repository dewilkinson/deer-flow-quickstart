import asyncio
import logging
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage
from pydantic import BaseModel
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.graph.nodes.common_vli import _run_node_with_tiered_fallback
from src.prompts.planner_model import Plan

async def run_test():
    class DummyRunnable:
        # Mock up an LCEL chain (no model attribute on the root object)
        def with_structured_output(self, schema):
            return self
        
        def invoke(self, *args, **kwargs):
            raise Exception("429 RESOURCE_EXHAUSTED")
            
    class DummyLLM:
        model = "models/gemini-3-flash-preview"
        def bind_tools(self, tools):
            return DummyRunnable()
            
        def invoke(self, *args, **kwargs):
            raise Exception("429 RESOURCE_EXHAUSTED")

    state = {"messages": []}
    config = {}

    try:
        from src.graph.nodes.common_vli import _run_node_with_tiered_fallback
        
        async def dummy_run_node(*args, **kwargs):
            with patch('src.graph.nodes.common_vli.create_agent_from_registry') as mock_create:
                with patch('src.graph.nodes.common_vli.get_llm_by_type') as mock_get_llm:
                    mock_create.return_value = DummyRunnable()
                    mock_get_llm.return_value = DummyLLM()
                    
                    return await _run_node_with_tiered_fallback("coordinator", state, config, messages=[AIMessage(content="test")])
        
        result, fallback = await dummy_run_node()
        
        print("====== RESULT ======")
        combined_text = result.content if hasattr(result, 'content') else str(result)
        for msg in fallback:
            combined_text += "\n" + msg.content
            
        print(combined_text)
        if "Gemini 3 Pro" in combined_text:
            print("\n[VULNERABILITY DETECTED]: The system still outputs 'Gemini 3 Pro' when an LCEL runnable is provided without a 'model' attribute!")
        elif "Gemini 3 Flash" in combined_text:
            print("\n[TEST PASSED]: Correctly extracted Gemini 3 Flash!")
            
    except Exception as e:
        print(f"Failed to run test. {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
