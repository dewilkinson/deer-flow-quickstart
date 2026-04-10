import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.server.app import _invoke_vli_agent

async def main():
    print("Testing ETHUSDT invoke directly...")
    try:
        response, state = await _invoke_vli_agent("Analyze ETHUSDT")
        print("\n--- RESPONSE ---")
        print(f"Type: {type(response)}")
        print(f"Length: {len(response)}")
        print(f"Repr: {repr(response)}")
        print("\n--- FINAL REPORT IN STATE ---")
        fr = state.get("final_report", "<NOT SET>")
        print(f"Repr: {repr(fr)}")
        print(f"Length: {len(fr) if isinstance(fr, str) else 'N/A'}")
        print("\n--- MESSAGES TRACE ---")
        for m in state.get("messages", []):
            name = getattr(m, 'name', 'unknown')
            print(f"[{type(m).__name__} | {name}]: {str(m.content)[:50]}...")
    except Exception as e:
        print(f"FATAL ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
