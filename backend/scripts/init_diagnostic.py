import asyncio
import os
import sys

import logging

# Add backend to path so 'src.*' imports resolve
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Enable trace-level diagnostics
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_init')

async def test_initialization():
    print("Testing System Initialization...")
    
    try:
        from src.services.macro_registry import MacroRegistry
        from src.tools.finance import get_macro_symbols
        print("[OK] Modules imported successfully.")
        
        print("Initializing Macro Registry...")
        registry = MacroRegistry()
        symbols = registry.get_macros()
        logger.debug(f"[OK] Watchlist loaded: {symbols}")
        
        logger.info("Testing Finance Engine Initialization (fetch fast_update)...")
        # Fetching data for a single symbol to test engine initialization
        logger.debug("Calling get_macro_symbols.ainvoke on ['SPY']")
        result = await get_macro_symbols.ainvoke({"symbols": ["SPY"], "fast_update": True})
        logger.debug(f"[OK] Engine generated telemetry payload successfully. Result keys: {result.keys() if isinstance(result, dict) else type(result)}")
        
        if isinstance(result, dict) and "SPY" in result:
            logger.info("[SUCCESS] Standalone Initialization Complete. Engine is operational. Result payload: " + str(result))
        else:
            logger.warning(f"[WARN] Initialization completed, but payload was malformed: {result}")
            
    except Exception as e:
        logger.error(f"[ERROR] System initialization failed! Exception: {str(e)}", exc_info=True)

if __name__ == "__main__":
    logger.info("Starting script...")
    asyncio.run(test_initialization())
