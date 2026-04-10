import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.graph.builder import build_graph

async def test_live_fetch():
    app = build_graph()
    
    print("\n[LIVE DIAGNOSTIC] Initiating SMC Analysis Fetch for $AAPL...\n" + "-"*50)
    config = {"configurable": {"thread_id": "live-fetch-test-sem-2"}}
    state = {"messages": [("user", "Run a deep SMC analysis on AAPL.")]}
    
    async for event in app.astream(state, config, stream_mode="updates"):
        for node_name, node_output in event.items():
            print(f"[TRANSITION] ---> Node '{node_name}' Finished.")
            # Print the final report if it exists
            if "final_report" in node_output:
                print("\n[OUTPUT DELIVERED]:\n" + "-"*50)
                print(node_output["final_report"])
                print("-" * 50)
                
if __name__ == "__main__":
    asyncio.run(test_live_fetch())
