import asyncio
import os
import sys
import time
import logging
import traceback

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure logging for debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AnalyzePipelineTest")

# Mock environment variables to bypass heavy initializations
os.environ["VLI_TEST_MODE"] = "True"
os.environ["RESEARCH_DB_URL"] = "sqlite:///:memory:" # Use in-memory SQLite to avoid PostgreSQL hang

async def run_stage(symbol: str, agent_func):
    logger.info(f"--- STARTING STAGE: {symbol} ---")
    start_time = time.time()
    prompt = f"Analyze {symbol}"
    
    try:
        # Use asyncio.wait_for to enforce 60s timeout
        logger.info(f"Invoking VLI Agent for: {symbol}")
        # Note: _invoke_vli_agent returns (response, final_state)
        response, state = await asyncio.wait_for(agent_func(prompt), timeout=120.0)
        
        duration = time.time() - start_time
        
        # Verify Report Quality
        is_long_form = "###" in response and len(response) > 50
        
        if is_long_form:
            logger.info(f"SUCCESS: {symbol} completed in {duration:.2f}s")
            logger.info(f"Report Preview (100 chars): {response[:100].replace('\n', ' ')}...")
            return True
        else:
            logger.error(f"FAILURE: {symbol} returned unexpected/short report in {duration:.2f}s")
            logger.info(f"Response Content: {response}")
            return False
            
    except asyncio.TimeoutError:
        duration = time.time() - start_time
        logger.error(f"FAILURE: {symbol} TIMED OUT after {duration:.2f}s")
        return False
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"FAILURE: {symbol} CRASHED after {duration:.2f}s: {e}")
        traceback.print_exc()
        return False

async def main():
    logger.info("Initializing VLI Graph and Dependencies (Attempting Direct Function Import)...")
    try:
        # Avoid shadowed 'app' by importing the function directly from the module
        from src.server.app import _invoke_vli_agent as agent_func
        logger.info("Initialization Successful.")
    except Exception as e:
        logger.error(f"Failed to initialize VLI Agent: {e}")
        traceback.print_exc()
        sys.exit(1)

    symbols = ["APA", "ETHUSDT"]
    results = []
    
    for symbol in symbols:
        success = await run_stage(symbol, agent_func)
        results.append((symbol, success))
        if not success:
            logger.error(f"Pipeline stalled at {symbol}. Investigate tool logs for hangs.")

    logger.info("\n=== PIPELINE TEST RESULTS ===")
    all_passed = True
    for symbol, success in results:
        status = "PASSED" if success else "FAILED"
        logger.info(f"- {symbol}: {status}")
        if not success:
            all_passed = False
            
    if all_passed:
        logger.info("PIPELINE VERIFIED: All 5 symbols analyzed within 60s each.")
    else:
        logger.error("PIPELINE FAILURE: One or more symbols failed.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
