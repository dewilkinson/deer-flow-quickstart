import asyncio
import logging
from unittest.mock import patch
from langchain_core.messages import AIMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.graph.nodes.common_vli import _run_node_with_tiered_fallback

async def run_test():
    class DummyRunnable:
        def invoke(self, *args, **kwargs):
            raise Exception("429 RESOURCE_EXHAUSTED")
            
    class DummyLLM:
        model = "models/gemini-3-flash-preview"
        def invoke(self, *args, **kwargs):
            raise Exception("429 RESOURCE_EXHAUSTED")

    try:
        # Patch BOTH so the underlying code actually uses them!
        with patch('src.agents.create_agent_from_registry', return_value=DummyRunnable()):
            with patch('src.llms.llm.get_llm_by_type', return_value=DummyLLM()):
                state = {"messages": []}
                config = {}
                result, fallback = await _run_node_with_tiered_fallback("coordinator", state, config, messages=[AIMessage(content="test")])
                
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
