import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.server.app import _invoke_vli_agent

async def main():
    try:
        print("--- RUNNING APA ---")
        response1, state1 = await _invoke_vli_agent("Analyze APA")
        print(f"APA Completed. Length: {len(response1)}")
        
        print("\n--- RUNNING ETHUSDT ---")
        response, state = await _invoke_vli_agent("Analyze ETHUSDT")
        
        with open("debug_eth_clean.txt", "w", encoding="utf-8") as f:
            f.write(f"Type: {type(response)}\n")
            f.write(f"Length: {len(response) if isinstance(response, str) else 'N/A'}\n")
            f.write(f"Response Repr: {repr(response)}\n")
            
            f.write("\n--- FINAL REPORT IN STATE ---\n")
            fr = state.get("final_report", "<NOT SET>")
            f.write(f"Repr: {repr(fr)}\n")
            
    except Exception as e:
        print(f"FATAL ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
