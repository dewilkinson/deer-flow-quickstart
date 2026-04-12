import asyncio
import time
import logging
import os
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from src.graph.nodes.vli import vli_node
from src.graph.nodes.reporter import reporter_node
from src.graph.nodes.common_vli import _compact_history
from src.config.configuration import Configuration

# Force debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("trace_diagnostics")

async def run_trace():
    print("\n" + "="*50)
    print("VLI TRACE DIAGNOSTIC: NVIDIA PERFORMANCE QUERY")
    print("="*50)
    
    query = "how has nvidia performed this year"
    
    state = {
        "messages": [HumanMessage(content=query)],
        "agent_type": "coordinator",
        "steps_completed": 0
    }
    
    config = {
        "configurable": {
            "execution_start_time": time.time(),
            "thread_id": "trace_diag_thread"
        }
    }
    
    # --- PHASE 1: SPINE (PARSER/ROUTING) ---
    print("\n[STEP 1] Executing VLI Spine (Parser/Routing)...")
    try:
        command = await vli_node(state, config)
        print(f"Command Target: {command.goto}")
        print(f"Command Update Keys: {command.update.keys()}")
        
        # Merge state
        state.update(command.update)
        msgs = state["messages"]
        print(f"Post-Spine Message Count: {len(msgs)}")
        for i, m in enumerate(msgs):
            name = getattr(m, 'name', 'None')
            print(f"  [{i}] {m.type.upper()} ({name}): {str(m.content)[:100]}...")
            
    except Exception as e:
        print(f"[ERROR] Spine execution failed: {e}")
        return

    # --- PHASE 2: INTERMEDIATE NODES (If any) ---
    # In Fast-Path, Spine goes directly to reporter.
    # In Slow-Path, it goes to coordinator, then reporter.
    
    if command.goto == "reporter":
        print("\n[STEP 2] Fast-Path detected. Skipping Coordinator.")
    else:
        print(f"\n[STEP 2] Slow-Path detected. Executing {command.goto}...")
        # For simplicity in this trace, we assume coordinator if not reporter
        # In a real graph we'd loop, but here we want to trace the reporter's input.
        pass

    # --- PHASE 3: REPORTER ---
    print("\n[STEP 3] Executing Reporter...")
    
    # We simulate the reporter's internal compaction to see what it sees
    print("\n[REPORTER_INTERNAL] Preparing Synthesis History...")
    compacted = _compact_history(state["messages"])
    print(f"Compacted History Count: {len(compacted)}")
    for i, m in enumerate(compacted):
        name = getattr(m, 'name', 'None')
        print(f"  [{i}] {m.type.upper()} ({name}): {str(m.content)[:100]}...")
        
    if len(compacted) <= 1:
         print("[WARNING] Reporter will see VERY LITTLE data. Check compaction logic!")

    try:
        final_result = await reporter_node(state, config)
        report = final_result.get("final_report", "")
        print("\n" + "-"*30)
        print("FINAL VLI REPORT")
        print("-"*30)
        print(report)
        print("-"*30)
        
        if "Information not provided" in report:
            print("\n[CRITICAL] Error Reproduced! Reporter claimed missing data.")
            # Check for structural exception signatures in messages
            if any("system_fallback" in getattr(m, "name", "") for m in final_result["messages"]):
                print("[ANALYSIS] Structural Exception occurred during Reporter phase.")
        else:
            print("\n[OK] Reporter produced a narrative.")
            
    except Exception as e:
        print(f"[ERROR] Reporter execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_trace())
