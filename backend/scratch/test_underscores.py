from src.graph.nodes.reporter import _sanitize_final_content

def test_underscores():
    text = "The analysis is complete. The specialist determined that has_enough_context is true for this ticker."
    sanitized = _sanitize_final_content(text)
    if not sanitized:
        print("[CRITICAL BUG] Semantic trigger confirmed with underscores!")
    else:
        print("[OK] Underscores allowed.")

if __name__ == "__main__":
    test_underscores()
