import asyncio
import logging
import sys
import os
from unittest.mock import MagicMock, patch

# Ensure PYTHONPATH includes backend
sys.path.append(os.path.join(os.getcwd(), "backend"))

from src.prompts.planner_model import Plan, Step, StepType
from src.graph.nodes.vli import vli_node
from langchain_core.messages import HumanMessage, AIMessage

# Setup logging to see the recovery errors
logging.basicConfig(level=logging.INFO)

async def test_malformed_plan_recovery():
    print("Testing malformed plan recovery in VLI Spine...")
    
    # 1. State with a malformed plan (dict that Plan(**plan) will fail on)
    state = {
        "messages": [HumanMessage(content="test query")],
        "current_plan": {"garbage": "data"}, # This will fail Plan(**dict)
        "steps_completed": 0,
        "intent": "MARKET_INSIGHT"
    }
    
    config = {"configurable": {"thread_id": "test"}}
    
    # 2. Mock the LLM and tool calls to focus on the reconstruction logic
    with patch("src.graph.nodes.vli.get_llm_by_type") as mock_llm, \
         patch("src.graph.nodes.common_vli._run_node_with_tiered_fallback") as mock_fallback, \
         patch("src.graph.nodes.common_vli.get_orchestrator_tools") as mock_tools:
        
        # Mocking the fallback to return a valid Plan and no fallback messages
        mock_fallback.return_value = (
            Plan(
                locale="en-US", 
                has_enough_context=True, 
                thought="Testing", 
                title="Test", 
                direct_response="OK"
            ),
            []
        )
        
        # 3. Call vli_node
        try:
            command = await vli_node(state, config)
            print("Successfully called vli_node without crashing.")
            
            # 4. Verify that recovery logs were triggered (implicitly by not crashing)
            # and that current_plan in the update is a valid Plan object
            updated_plan = command.update.get("current_plan")
            if isinstance(updated_plan, Plan):
                print(f"PASS: current_plan was recovered as a Plan object. Title: {updated_plan.title}")
            else:
                print(f"FAIL: current_plan is still {type(updated_plan)}")
                
        except Exception as e:
            print(f"FAIL: vli_node crashed with error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_malformed_plan_recovery())
