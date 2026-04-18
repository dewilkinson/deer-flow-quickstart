import asyncio
import os
import sys

# Ensure correct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.graph.nodes.parser import parser_node
from src.graph.types import State
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

async def test_vli_aapl():
    print("Simulating VLI session for 'get aapl price'...")
    state: State = {
        "messages": [HumanMessage(content="get aapl price")],
        "task": "get aapl price",
        "current_plan": None,
        "final_report": "",
        "direct_mode": False
    }
    
    config: RunnableConfig = {
        "configurable": {
            "thread_id": "test_thread",
            "checkpoint_ns": "vli",
            "checkpoint_id": "1"
        }
    }
    
    # Run Parser
    res = await parser_node(state, config)
    print(f"Parser Result: {res}")
    
    # If it triggered fast-path, we'll see Command(goto='__end__')
    # and update={'final_report': '...', 'messages': [...]}
    if hasattr(res, 'update'):
        update = res.update
        if 'final_report' in update:
            print(f"FINAL REPORT: {update['final_report']}")
        if 'messages' in update:
            for m in update['messages'][-2:]:
                print(f"Message: {m.type} - {str(m.content)[:100]}...")

if __name__ == "__main__":
    asyncio.run(test_vli_aapl())
