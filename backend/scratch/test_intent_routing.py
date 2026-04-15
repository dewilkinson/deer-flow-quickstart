import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')
from src.graph.builder import build_graph
from langchain_core.messages import HumanMessage

async def test_routing(query: str):
    print(f"\n[TESTING] Query: {query}")
    graph = build_graph()
    state = {
        "messages": [HumanMessage(content=query)],
        "intent_mode": "TACTICAL_EXECUTION",
        "current_plan": None
    }
    
    config = {"configurable": {"vli_llm_type": "reasoning"}}
    
    async for chunk in graph.astream(state, config=config):
        for node, values in chunk.items():
            if node == "vli_parser": # The node name is likely 'vli_parser' or 'vli'
                plan = values.get("current_plan")
                if plan:
                    step_type = plan.steps[0].step_type if plan.steps else "DIRECT"
                    print(f"Node: {node} | Forced Step Type: {step_type} | Title: {plan.title}")
                    return
            # Also check coordinator just in case
            if node == "coordinator":
                plan = values.get("current_plan")
                if plan:
                    step_type = plan.steps[0].step_type if plan.steps else "DIRECT"
                    print(f"Node: {node} | Forced Step Type: {step_type} | Title: {plan.title}")
                    return

async def main():
    queries = [
        "describe what smc means",
        "What is RSI?",
        "get NVDA smc analysis",
        "recommend a strategy for BTC",
        "How about eth analysis?",
        "eth analysis",
    ]
    
    for q in queries:
        await test_routing(q)

if __name__ == "__main__":
    asyncio.run(main())
