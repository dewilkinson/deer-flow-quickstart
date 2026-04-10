
import asyncio
import logging
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage
from pydantic import ValidationError

# Setup logger for visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the logic to test
import sys
import os
sys.path.append(os.getcwd())

from src.graph.nodes.common_vli import _run_node_with_tiered_fallback
from src.prompts.planner_model import Plan

async def test_reproduce_429_structural_failure():
    print("\n[TEST] Reproducing 429 Structural Parsing Failure...")
    
    # tier_0_mock: Simulates Reasoning tier throwing a Validation Error (Common on 429 garbage)
    tier_0_mock = MagicMock()
    st_mock_0 = MagicMock()
    # Simulate a Pydantic Validation error
    st_mock_0.invoke = AsyncMock(side_effect=ValueError("429 RESOURCE_EXHAUSTED: Expected dict, got string"))
    tier_0_mock.with_structured_output = MagicMock(return_value=st_mock_0)
    
    # tier_1_mock: Simulates Flash success
    tier_1_mock = MagicMock()
    valid_plan = {
        "thought": "Fallback successful", 
        "has_enough_context": True, 
        "direct_response": "Test Success", 
        "title": "Fallback", 
        "steps": [],
        "locale": "en-US"
    }
    st_mock_1 = MagicMock()
    st_mock_1.invoke = AsyncMock(return_value=valid_plan)
    tier_1_mock.with_structured_output = MagicMock(return_value=st_mock_1)

    async def mock_to_thread(func, *args, **kwargs):
        return await func(*args, **kwargs)

    with patch('src.llms.llm.get_llm_by_type') as mock_get_llm, \
         patch('asyncio.to_thread', side_effect=mock_to_thread):
        
        def side_effect(tier_type):
            if tier_type == "reasoning": return tier_0_mock
            return tier_1_mock
            
        mock_get_llm.side_effect = side_effect
        state = {"messages": [], "is_test_mode": True}
        config = {"configurable": {"thread_id": "test_thread"}}
        
        try:
            print("[PROCESS] Running _run_node_with_tiered_fallback...")
            # If all tiers fail, this should raise an exception that vli.py catches
            result, fb_msgs = await _run_node_with_tiered_fallback("coordinator", state, config, is_structured=True, structured_schema=Plan)
            
            print(f"[RESULT] Final Plan Title: {result.get('title') if isinstance(result, dict) else getattr(result, 'title', 'None')}")
            
            # If we got here, it means we fell back to basic successfully
            if "Fallback" in str(result):
                print("\n[SUCCESS] Fallback worked for structural failure!")
            else:
                print("\n[FAILURE] Fallback did not happen correctly.")

        except Exception as e:
            print(f"\n[CRASH] The system raised exception: {e}")

from unittest.mock import AsyncMock

if __name__ == "__main__":
    asyncio.run(test_reproduce_429_structural_failure())
