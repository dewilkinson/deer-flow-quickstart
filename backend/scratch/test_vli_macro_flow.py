import asyncio
import os
import sys
import logging

# Ensure backend/src is in pythonpath
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import HumanMessage
from src.graph.builder import build_graph

# Force debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_flow")

async def run_test():
    print("\n" + "="*50)
    print("VLI GRAPH TEST: MACRO FLOW")
    print("="*50)
    
    query = "how have the markets performed today"
    graph = build_graph()
    
    state = {
        "messages": [HumanMessage(content=query)],
        "agent_type": "coordinator",
        "steps_completed": 0,
        "is_test_mode": True,
        "is_plan_approved": True
    }
    
    config = {
        "configurable": {
            "thread_id": "test_macro_flow_1"
        }
    }
    
    print("\nInvoking Graph...")
    try:
        # Await the execution of the entire graph logic
        result = await graph.ainvoke(state, config)
        print("\n" + "-"*30)
        print("FINAL GRAPH MESSAGES:")
        print("-" * 30)
        
        for m in result.get("messages", []):
            name = getattr(m, 'name', '') or ''
            print(f"[{m.type.upper()}] {name}: {str(m.content)[:300]}...")
            
    except Exception as e:
        print(f"\n[ERROR] Graph execution crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_test())
