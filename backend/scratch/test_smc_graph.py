import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.graph.builder import build_graph

async def test_nvda_smc():
    graph = build_graph()
    
    state = {
        "messages": [HumanMessage(content="get NVDA smc analysis")],
        "intent_mode": "TACTICAL_EXECUTION",
        "current_plan": None
    }
    
    config = {
        "configurable": {
            "vli_llm_type": "reasoning",
            "reporter_llm_type": "reasoning"
        }
    }
    
    print("\n--- RUNNING GRAPH ---")
    async for chunk in graph.astream(state, config=config):
        for node, values in chunk.items():
            print(f"\nNode: {node}")
            if "messages" in values and values["messages"]:
                last_msg = values["messages"][-1]
                if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                    print(f"[TOOL_CALLS] {last_msg.tool_calls}")
                elif isinstance(last_msg, ToolMessage):
                    print(f"[TOOL_RESULT] {last_msg.name}: {last_msg.content[:500]}...")
                else:
                    print(f"[{last_msg.type}] {last_msg.content[:500]}...")

if __name__ == "__main__":
    asyncio.run(test_nvda_smc())
