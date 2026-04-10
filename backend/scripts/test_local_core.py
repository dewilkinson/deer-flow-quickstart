import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from src.llms.llm import get_llm_by_type
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_core_init():
    logger.info("--- Testing Gemma 4 Core Initialization (LOCAL) ---")
    try:
        # 1. Test direct CORE_MODEL initialization
        core_llm = get_llm_by_type("core")
        logger.info(f"SUCCESS: Core LLM object: {type(core_llm)}")
        
        # Flexibly get model name based on class
        if hasattr(core_llm, "model_name"): # ChatOpenAI (Ollama)
            model_id = core_llm.model_name
        elif hasattr(core_llm, "model"): # ChatGoogleGenerativeAI
            model_id = core_llm.model
        else:
            model_id = "unknown"
            
        logger.info(f"Detected Model ID: {model_id}")
        
        if "gemma4" in model_id.lower() or "gemma-4" in model_id.lower():
            logger.info("PASSED: Correct Core model detected.")
            
            # ACTUAL INVOCATION TEST
            logger.info("--- Testing Core Invocation (Ollama Local) ---")
            response = core_llm.invoke("Hello. Respond with one word: 'Operational'.")
            logger.info(f"RESPONSE: {response.content}")
        else:
            logger.error(f"FAILED: Unexpected model ID '{model_id}'")

    except Exception as e:
        logger.error(f"CRITICAL: Core initialization failed: {e}")

if __name__ == "__main__":
    test_core_init()
