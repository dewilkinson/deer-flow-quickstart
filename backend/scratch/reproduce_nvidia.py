import asyncio
import time
import logging
from langchain_core.messages import HumanMessage
from src.graph.nodes.common_vli import _run_node_with_tiered_fallback
from src.config.configuration import Configuration

# Ensure we see all trace logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reproduce_nvidia")

async def reproduce():
    print("\n--- REPRODUCING NVIDIA QUERY ---")
    query = "how has nvidia performed this year"
    
    # Mocking the state and config
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
    
    print(f"Executing query: {query}")
    
    try:
        # We start with the coordinator as it's the most likely to trigger a structural exception or routing failure
        result, fallback_messages = await _run_node_with_tiered_fallback(
            "coordinator", 
            state, 
            config, 
            messages=state["messages"]
        )
        
        print("\n--- RESULT ---")
        print(f"Type: {type(result)}")
        print(f"Content: {result}")
        
        print("\n--- FALLBACK MESSAGES ---")
        for m in fallback_messages:
            print(f"- {m.content}")
            
    except Exception as e:
        print(f"\n[CRITICAL ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(reproduce())
