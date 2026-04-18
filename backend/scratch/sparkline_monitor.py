import asyncio
import time
import json
from src.tools.macros import fetch_market_macros

async def monitor():
    history = {}
    print("Starting Sparkline Monitor... (Checking every 15s)")
    for step in range(80): # 20 minutes doing 15s intervals
        print(f"[{time.strftime('%H:%M:%S')}] Monitoring step {step+1}/80...")
        
        # Trigger the fetch
        result = await fetch_market_macros.ainvoke({})
        try:
            if isinstance(result, str):
                result = json.loads(result)
            
            rows = result.get('rows', [])
            for row in rows:
                ticker = row[1]
                sparkline_cell = row[5]
                if isinstance(sparkline_cell, dict) and sparkline_cell.get('type') == 'sparkline':
                    vals = sparkline_cell.get('value', [])
                    
                    if not vals:
                        continue
                        
                    # Is it flatline?
                    last_val = vals[-1]
                    flat_count = 0
                    for v in reversed(vals):
                        if v == last_val:
                            flat_count += 1
                        else:
                            break
                            
                    is_flat = flat_count > len(vals) * 0.85  # 85% flat
                    
                    if ticker not in history:
                        history[ticker] = {'was_populated': not is_flat, 'snapshots': []}
                        
                    history[ticker]['snapshots'].append(vals)
                    
                    if history[ticker]['was_populated'] and is_flat:
                        print(f"\n[ALERT] {ticker} has gone FLAT!")
                        print(f"Previous valid snapshot: {history[ticker]['snapshots'][-2]}")
                        print(f"Current flat snapshot  : {vals}")
                        with open("scratch/sparkline_flat_alert.json", "w") as f:
                            json.dump(history[ticker]['snapshots'], f)
                        return
                    
                    history[ticker]['was_populated'] = not is_flat
                    
        except Exception as e:
            print(f"Error parsing: {e}")
            
        await asyncio.sleep(15)
        
    print("Completed monitoring with no transitions to flatline detected.")

if __name__ == "__main__":
    asyncio.run(monitor())
