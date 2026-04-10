import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.server.app import _invoke_vli_agent

async def main():
    try:
        response, state = await _invoke_vli_agent("Analyze ETHUSDT")
        
        with open("debug_eth_clean.txt", "w", encoding="utf-8") as f:
            f.write(f"Type: {type(response)}\n")
            f.write(f"Length: {len(response)}\n")
            f.write(f"Response Repr: {repr(response)}\n")
            
            f.write("\n--- FINAL REPORT IN STATE ---\n")
            fr = state.get("final_report", "<NOT SET>")
            f.write(f"Repr: {repr(fr)}\n")
            f.write(f"Length: {len(fr) if isinstance(fr, str) else 'N/A'}\n")
            
            f.write("\n--- MESSAGES TRACE ---\n")
            for i, m in enumerate(state.get("messages", [])):
                name = getattr(m, 'name', 'unknown')
                f.write(f"[{i} | {type(m).__name__} | {name}]: {str(m.content)[:100]}\n")
    except Exception as e:
        with open("debug_eth_clean.txt", "w", encoding="utf-8") as f:
            f.write(f"FATAL ERROR: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())
