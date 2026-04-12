import asyncio
import time
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from src.graph.nodes.common_vli import _compact_history

def debug_compaction():
    print("\n--- DEEP HISTORY COMPACTION AUDIT ---")
    
    # Simulate a complex history where a fallback occurred
    messages = [
        HumanMessage(content="how has nvidia performed this year"),
        AIMessage(content="I will check NVIDIA.", name="coordinator"),
        AIMessage(content="[SYSTEM_FALLBACK] Reasoning tier 429. Falling back to basic.", name="system_fallback"),
        AIMessage(content="NVIDIA has performed well. Price: $120. Growth: 150%.", name="vli_coordinator")
    ]
    
    print("Pre-compaction profile:")
    for i, m in enumerate(messages):
        name = getattr(m, 'name', 'None')
        print(f"  [{i}] {name}: {str(m.content)[:50]}...")
        
    compacted = _compact_history(messages)
    
    print("\nPost-compaction profile:")
    for i, m in enumerate(compacted):
        name = getattr(m, 'name', 'None')
        print(f"  [{i}] {name}: {str(m.content)[:50]}...")

    if not any("NVIDIA" in str(m.content) for m in compacted):
        print("\n[CRITICAL BUG] Data lost despite fix!")
    else:
        print("\n[INFO] Data preserved.")

if __name__ == "__main__":
    debug_compaction()
