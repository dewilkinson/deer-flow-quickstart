import asyncio
import json
from src.tools.finance import get_macro_symbols

async def test_macro_json():
    print("--- VLI Sparkline Data Integration Verification ---")
    try:
        # Execute the macro tool
        res_json = await get_macro_symbols.ainvoke({})
        data = json.loads(res_json)
        
        print(f"Response Type: {data.get('type')}")
        print(f"Headers: {data.get('headers')}")
        
        if data.get("type") == "table":
            print("SUCCESS: Tool correctly returned structural JSON table.")
        else:
            print("FAILED: Tool returned incorrect format.")
            
        rows = data.get("rows", [])
        if rows:
            first_row = rows[0]
            print(f"Sample Row: {first_row}")
            # Check for sparkline object
            sparkline_cell = next((c for c in first_row if isinstance(c, dict) and c.get("type") == "sparkline"), None)
            if sparkline_cell:
                print(f"SUCCESS: Sparkline data detected (Points: {len(sparkline_cell.get('value', []))})")
                if len(sparkline_cell.get('value', [])) > 5:
                    print("Verify: Sparkline resolution is sufficient.")
                else:
                    print("WARNING: Sparkline data is sparse.")
            else:
                print("FAILED: Sparkline data missing from rows.")
        else:
            print("FAILED: No rows returned.")
            
    except Exception as e:
        print(f"CRASHED: {e}")

if __name__ == "__main__":
    asyncio.run(test_macro_json())
