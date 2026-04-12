import asyncio
import time
from langchain_core.messages import HumanMessage, AIMessage
from src.graph.nodes.vli import vli_node
from src.graph.nodes.reporter import reporter_node
from src.config.configuration import Configuration

async def test_full_nvidia_flow():
    print("\n--- TESTING FULL NVIDIA FLOW ---")
    query = "how has nvidia performed this year"
    
    # 1. Start state
    state = {
        "messages": [HumanMessage(content=query)],
        "agent_type": "coordinator"
    }
    
    config = {
        "configurable": {
            "execution_start_time": time.time(),
            "thread_id": "test_nvidia_thread"
        }
    }
    
    # 2. Run VLI Spine (Coordinator)
    print("Step 1: Running VLI Spine...")
    res1 = await vli_node(state, config)
    
    # Extract updated state from Command
    updated_state = state.copy()
    updated_state.update(res1.update)
    
    print(f"Spine transition to: {res1.goto}")
    print(f"New messages count: {len(updated_state['messages'])}")
    
    # 3. Run Reporter
    print("\nStep 2: Running Reporter...")
    res2 = await reporter_node(updated_state, config)
    
    final_report = res2.get("final_report", "")
    print("\n--- FINAL REPORT ---")
    print(final_report)
    
    if "Information not provided" in final_report:
        print("\n[FAIL] Reporter still claims data is missing!")
    elif "NVIDIA" in final_report or "NVDA" in final_report:
        print("\n[SUCCESS] NVIDIA data preserved and reported!")
    else:
        print("\n[WARNING] NVIDIA not found in report, but 'No Data' was avoid. check text.")

if __name__ == "__main__":
    asyncio.run(test_full_nvidia_flow())
