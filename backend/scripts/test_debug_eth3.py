import asyncio
import sys
import os
import traceback

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.server.app import _invoke_vli_agent
from src.tools.finance import get_stock_quote

async def main():
    try:
        response, state = await _invoke_vli_agent("Analyze ETHUSDT")
        
        print("Response Type:", type(response))
        print("Response Length:", len(response) if isinstance(response, str) else "N/A")
        print("Response Repr:", repr(response))
        
        print("\n--- FINAL REPORT IN STATE ---")
        fr = state.get("final_report", "<NOT SET>")
        print("Repr:", repr(fr))
        
        print("\n--- MESSAGES TRACE ---")
        for i, m in enumerate(state.get("messages", [])):
            name = getattr(m, 'name', 'unknown')
            cls = type(m).__name__
            content = str(getattr(m, 'content', ''))
            print(f"[{i} | {cls} | {name}]: {content[:150]}...")
            if hasattr(m, 'tool_calls') and m.tool_calls:
                print(f"    Tool Calls: {m.tool_calls}")
    except Exception as e:
        print("FATAL ERROR:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
