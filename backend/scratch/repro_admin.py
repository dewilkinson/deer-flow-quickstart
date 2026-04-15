import asyncio
from src.graph.builder import build_graph
from src.graph.types import State
from src.prompts.planner_model import Plan, Step, StepType
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import sys
import os

# Set dummy key if not present
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = "mock_key"

async def test_admin_fast_path_hardened():
    graph = build_graph()
    
    query = "invalidate cache"
    print(f"\n--- TESTING QUERY: {query} (HARDENED) ---")
    
    # Simulate a state where the plan has been converted to a dictionary
    # This mimics the LangGraph checkpointer behavior
    mock_plan_dict = {
        "title": "System Cache Invalidation",
        "thought": "Direct admin directive.",
        "locale": "en-US",
        "steps": [
            {
                "title": "Invalidate Market Cache",
                "description": "FAST_PATH_ADMIN: invalidate cache",
                "step_type": "system",
                "need_search": False
            }
        ],
        "intent": "EXECUTE_DIRECT",
        "has_enough_context": False
    }
    
    initial_state = {
        "messages": [
            HumanMessage(content=query),
            AIMessage(content="[VLI_SPINE] Plan generated: System Cache Invalidation", name="vli_coordinator"),
            ToolMessage(content="Cache successfully invalidated.", tool_call_id="call_123", name="invalidate_market_cache"),
            AIMessage(content="SYSTEM task completed successfully.", name="system_finalize")
        ],
        "current_plan": mock_plan_dict,
        "steps_completed": 1,
        "intent": "EXECUTE_DIRECT", # Propagated top-level intent
        "is_test_mode": True,
    }
    
    config = {"configurable": {"thread_id": "test_thread", "user_id": "test_user"}}
    
    # Invoke the graph specifically starting at VLI node after the specialist returned
    # By default, ainvoke starts at START. We want to see how VLI handles this state.
    # In LangGraph, when a node returns, the router is called.
    # Our VLI node IS the router/coordinator.
    
    from src.graph.nodes.vli import vli_node
    
    print("\n--- INVOKING VLI NODE WITH DICTIONARY PLAN ---")
    result = await vli_node(initial_state, config=config)
    
    print(f"\nRESULT GOTO: {result.goto}")
    
    if result.goto == "__end__" or str(result.goto) == "END":
        print("\nSUCCESS: VLI recognized the dictionary plan and top-level intent, bypassing reporter.")
    else:
        print(f"\nFAILURE: VLI still routing to {result.goto}")

if __name__ == "__main__":
    try:
        asyncio.run(test_admin_fast_path_hardened())
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
