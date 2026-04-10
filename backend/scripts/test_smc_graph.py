import asyncio
import os
import sys
import codecs
import logging
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))

logging.basicConfig(level=logging.DEBUG, filename='graph_actual_debug.log', filemode='w')

from langchain_core.messages import HumanMessage
from src.graph.builder import build_graph_with_memory
import io

async def main():
    graph = build_graph_with_memory()
    
    workflow_input = {
        "messages": [HumanMessage(content="Analyze AAPL")],
        "plan_iterations": 0,
        "steps_completed": 0,
        "final_report": "",
        "current_plan": None,
        "observations": [],
        "auto_accepted_plan": True,
        "is_plan_approved": True,
        "enable_background_investigation": False,
        "research_topic": "Analyze AAPL",
        "verbosity": 1,
        "direct_mode": False,
    }

    config = {
        "configurable": {
            "thread_id": "test_smc_123456",
            "max_plan_iterations": 0,
            "max_step_num": 5,
            "max_search_results": 2,
            "report_style": "concise",
            "direct_mode": False,
        },
        "recursion_limit": 50,
    }

    with open('graph_actual.txt', 'w', encoding='utf-8') as f:
        f.write("STARTING GRAPH\n")
        async for step in graph.astream(workflow_input, config=config):
            for node_name, state in step.items():
                f.write(f"--- NODE: {node_name} ---\n")
                if state.get('current_plan'):
                    f.write(f"plan.steps: {state.get('current_plan').steps}\n")
                f.write(f"steps_completed: {state.get('steps_completed')}\n")
                if state.get("messages"):
                    last_msg = state["messages"][-1]
                    f.write(f"last_msg: {getattr(last_msg, 'name', 'None')} -> {str(last_msg.content)[:80]}\n")
                f.write("-----------------------\n")
        f.write("DONE\n")

if __name__ == "__main__":
    asyncio.run(main())
