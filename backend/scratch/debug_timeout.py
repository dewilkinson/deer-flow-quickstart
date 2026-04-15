import asyncio
import logging
from langchain_core.messages import HumanMessage
from src.graph.builder import build_graph

logging.basicConfig(level=logging.DEBUG)

async def test_full_graph():
    print("Testing Full Graph Flow for Timeout Query...")
    graph = build_graph()
    
    query = "What would be a sound trading strategy to follow for this week"
    
    workflow_input = {
        "messages": [HumanMessage(content=query)],
        "plan_iterations": 0,
        "steps_completed": 0,
        "final_report": "",
        "current_plan": None,
        "observations": [],
        "auto_accepted_plan": True,
        "is_plan_approved": True,
        "enable_background_investigation": False,
        "research_topic": query[:100],
        "verbosity": 1,
        "direct_mode": False,
        "raw_data_mode": False,
        "intent": "MARKET_INSIGHT",
    }
    
    workflow_config = {
        "configurable": {
            "thread_id": "debug_timeout_1",
            "max_plan_iterations": 0,
            "max_step_num": 5,
            "max_search_results": 2,
            "report_style": "concise",
            "direct_mode": False,
            "reporter_llm_type": "reasoning",
            "vli_llm_type": "reasoning",
            "intent_mode": "MARKET_INSIGHT",
        },
        "recursion_limit": 50,
    }
    
    async for chunk in graph.astream(workflow_input, config=workflow_config):
        print("====== GRAPH NODE CHUNK ======")
        for k, v in chunk.items():
            print(f"Node: {k}")
            if "messages" in v:
                messages = v["messages"]
                for i, msg in enumerate(messages):
                    try:
                        print(f"  Msg[{i}] ({getattr(msg, 'name', msg.type)}): {str(msg.content)[:200]}...")
                    except:
                        pass
        print("==============================")

if __name__ == "__main__":
    asyncio.run(test_full_graph())
