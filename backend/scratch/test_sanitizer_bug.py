import asyncio
from src.graph.nodes.reporter import _sanitize_final_content

def test_semantic_trigger():
    print("\n--- TESTING SEMANTIC TRIGGER BUG ---")
    
    # Case 1: Healthy narrative that mentions one of the "keys" naturally
    healthy_text = "The analysis is complete. The system determined it has enough context to provide this NVIDIA report. NVDA is up 120%."
    
    sanitized = _sanitize_final_content(healthy_text)
    
    if not sanitized:
        print("[BUG REPRODUCED] Healthy text was sanitized because it mentioned 'has enough context'!")
    else:
        print("[SUCCESS] Healthy text preserved.")
        
    # Case 2: Actual JSON leak
    leaky_text = '{"thought": "test", "has_enough_context": true, "direct_response": "leak"}'
    sanitized_leak = _sanitize_final_content(leaky_text)
    
    if not sanitized_leak:
        print("[SUCCESS] Actual JSON leak caught.")
    else:
        print("[FAIL] Actual leak allowed!")

if __name__ == "__main__":
    test_semantic_trigger()
