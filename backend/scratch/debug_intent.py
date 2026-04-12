from src.server.app import _get_vli_intent

def debug_intent():
    # Test cases
    queries = [
        " how has nvidia performed this year",
        "Analyze NVDA",
        "What is the STRIKE price?",
        "Explain SMC concepts"
    ]
    
    for q in queries:
        print(f"'{q}' -> {_get_vli_intent(q)}")

if __name__ == "__main__":
    debug_intent()
