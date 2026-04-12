import os
import sys
from pathlib import Path

# Add backend/src to path
backend_path = Path(__file__).parent.parent.resolve()
sys.path.append(str(backend_path / "src"))
sys.path.append(str(backend_path))

import logging
logging.basicConfig(level=logging.INFO)

from src.llms.llm import get_llm_by_type

def verify_gemini():
    print("=== Gemini API Hardening Verification ===")
    
    # Check if .env is loaded correctly from backend/
    vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    print(f"Loaded Vault Path: {vault_path}")
    
    if not vault_path:
        print("[FAIL] .env not loaded correctly from backend/")
        return

    try:
        print("\nTesting 'reasoning' LLM instantiation (Gemini)...")
        llm = get_llm_by_type("reasoning")
        # ChatGoogleGenerativeAI uses 'model', not 'model_name'
        print(f"[SUCCESS] Reasoning LLM instantiated: {getattr(llm, 'model', 'Unknown')}")
        
        # Check for mirroring
        # Note: Depending on langchain version, this might be in dict or fields
        print(f"Model Name: {getattr(llm, 'model_name', 'Unknown')}")
        
        print("\nTesting 'basic' LLM instantiation (Gemini)...")
        basic_llm = get_llm_by_type("basic")
        print(f"[SUCCESS] Basic LLM instantiated: {basic_llm.model_name}")

    except Exception as e:
        print(f"[FAIL] Instantiation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_gemini()
