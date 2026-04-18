import asyncio
import logging
import sys
import os
import time
from datetime import datetime
from uuid import uuid4

# Set up paths
sys.path.append(os.getcwd())

from src.graph.builder import build_graph_with_memory
from langchain_core.messages import HumanMessage

async def full_graph_test():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("FULL_GRAPH_TEST")
    
    ticker = "APA"
    print(f"### FULL GRAPH UNIT TEST for {ticker}")
    
    graph = build_graph_with_memory()
    
    # Mock LangGraph state
    inputs = {
        "messages": [HumanMessage(content=f"Analyze {ticker}")],
        "metadata": {
            "user_id": "test_user",
            "thread_id": str(uuid4())
        }
    }
    
    config = {
        "configurable": {
            "thread_id": str(uuid4()),
            "execution_start_time": time.time(),
            "vli_llm_type": "reasoning"
        }
    }
    
    start_time = time.time()
    try:
        print(f"Executing graph.ainvoke for {ticker}...")
        # Use 130s to allow tiered fallbacks (60+35+30=125) to finish before the test itself times out
        result = await asyncio.wait_for(graph.ainvoke(inputs, config=config), timeout=130.0)
        end_time = time.time()
        
        print(f"\nSUCCESS in {end_time - start_time:.2f} seconds")
        print("\nRESULT KEYS:", result.keys())
        
        fr = result.get("final_report", "NO_REPORT")
        print(f"\nFINAL REPORT (First 500 chars):\n{str(fr)[:500]}...")
        
        # Log node durations if available in metadata
        messages = result.get("messages", [])
        for m in messages:
            name = getattr(m, "name", "unknown")
            dur = getattr(m, "additional_kwargs", {}).get("duration_secs", 0)
            if dur:
                print(f"Node: {name} | Duration: {dur:.2f}s")
            
    except asyncio.TimeoutError:
        print(f"\nTIMEOUT after {time.time() - start_time:.2f} seconds")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(full_graph_test())
