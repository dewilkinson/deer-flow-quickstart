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
    logger.info("--- Testing Gemma 4 Core Initialization ---")
    try:
        # 1. Test direct CORE_MODEL initialization
        core_llm = get_llm_by_type("core")
        logger.info(f"SUCCESS: Core LLM initialized as {type(core_llm)}")
        
        model_id = getattr(core_llm, "model", getattr(core_llm, "model_name", "unknown"))
        logger.info(f"Model ID: {model_id}")
        
        if "gemma4" in model_id.lower() or "gemma-4" in model_id.lower():
            logger.info("PASSED: Correct Gemma 4 model variant detected.")
            
            # ACTUAL INVOCATION TEST
            logger.info("--- Testing Gemma 4 Invocation (Hello World) ---")
            response = core_llm.invoke("Hello Gemma 4. Are you operational? Please respond with a short confirmation.")
            logger.info(f"RESPONSE CONTENT: {response.content}")
            if response.content:
                logger.info("PASSED: Gemma 4 is operational and responding.")
        else:
            logger.error(f"FAILED: Unexpected model ID '{model_id}'")

    except Exception as e:
        logger.error(f"CRITICAL: Failed to initialize Core LLM: {e}")

def test_research_init():
    logger.info("\n--- Testing Gemini 3 Flash Research Initialization ---")
    try:
        research_llm = get_llm_by_type("reasoning")
        logger.info(f"SUCCESS: Research LLM initialized as {type(research_llm)}")
        
        model_id = getattr(research_llm, "model", getattr(research_llm, "model_name", "unknown"))
        logger.info(f"Model ID: {model_id}")

    except Exception as e:
        logger.error(f"CRITICAL: Failed to initialize Research LLM: {e}")

if __name__ == "__main__":
    test_core_init()
    test_research_init()
