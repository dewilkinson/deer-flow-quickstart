import asyncio
from langchain_core.messages import AIMessage, HumanMessage
from src.graph.nodes.common_vli import _compact_history

def test_compaction():
    print("\n--- TESTING HISTORY COMPACTION ---")
    
    # Simulate a history where the VLI coordinator provides a direct answer
    messages = [
        HumanMessage(content="how has nvidia performed this year"),
        AIMessage(content="I will check NVIDIA's performance.", name="coordinator"),
        AIMessage(content="NVIDIA has performed exceptionally well, up 120% YTD...", name="vli_coordinator")
    ]
    
    print("Original names:", [getattr(m, 'name', 'None') for m in messages])
    
    compacted = _compact_history(messages)
    
    print("Compacted names:", [getattr(m, 'name', 'None') for m in compacted])
    print("Compacted contents:", [m.content for m in compacted])
    
    if not any("NVIDIA" in str(m.content) for m in compacted):
        print("\n[BUG CONFIRMED] Data lost during compaction!")
    else:
        print("\n[SUCCESS] Data preserved.")

if __name__ == "__main__":
    test_compaction()
