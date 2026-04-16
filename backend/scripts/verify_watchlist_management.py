import asyncio
import os
import json
from src.services.macro_registry import macro_registry
from src.tools.finance import manage_macro_watchlist

async def test_watchlist_mgmt():
    print("--- VLI Dynamic Watchlist Management Verification ---")
    
    # 1. Add a symbol
    print("Action: Add TSLA")
    res = await manage_macro_watchlist.ainvoke({"action": "add", "label": "TSLA", "ticker": "TSLA"})
    print(f"Result: {res}")
    
    macros = macro_registry.get_macros()
    if "TSLA" in macros:
        print("SUCCESS: TSLA persisted to registry.")
    else:
        print("FAILED: TSLA not found in registry.")

    # 2. Reset
    print("\nAction: Reset")
    res = await manage_macro_watchlist.ainvoke({"action": "reset"})
    print(f"Result: {res}")
    
    macros = macro_registry.get_macros()
    if "TSLA" not in macros and "VIX" in macros:
        print("SUCCESS: Registry factory reset successful.")
    else:
        print("FAILED: Registry reset did not restore defaults or remove TSLA.")

if __name__ == "__main__":
    asyncio.run(test_watchlist_mgmt())
