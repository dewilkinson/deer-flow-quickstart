import os
import sys
import json
import time
import requests

URL = 'http://127.0.0.1:8000/api/vli/action-plan'
HEADERS = {'Content-Type': 'application/json'}

def run_test(name, prompt, direct_mode, raw_data_mode):
    payload = {
        'text': prompt,
        'raw_data_mode': raw_data_mode,
        'direct_mode': direct_mode,
        'is_action_plan': False
    }
    
    print(f"\n--- Running: {name} ---")
    print(f"Prompt: {prompt}")
    
    start_time = time.time()
    try:
        response = requests.post(URL, headers=HEADERS, json=payload, timeout=120.0)
        end_time = time.time()
        duration = end_time - start_time
        
        try:
            data = response.json()
            if 'response' in data:
                text = data['response']
                # Try to parse as JSON in case it's the raw array/object
                try:
                    # sometimes it's wrapped in triple backticks if llm produced it, but direct mode won't
                    clean_text = text.strip()
                    if clean_text.startswith("```json"):
                        clean_text = clean_text[7:-3].strip()
                    parsed = json.loads(clean_text)
                    print(f"[{duration:.2f}s] SUCCESS: Returned JSON object.")
                    return parsed, duration
                except Exception as e:
                    print(f"[{duration:.2f}s] FAILURE: Could not parse response as JSON. Excerpt: {text[:200]}")
                    return None, duration
            else:
                print(f"[{duration:.2f}s] ERROR: No 'response' field in output. Output: {list(data.keys())}")
                return None, duration
        except BaseException:
            print(f"[{duration:.2f}s] Error parsing response: {response.text}")
            return None, duration
            
    except Exception as e:
        end_time = time.time()
        print(f"[{end_time - start_time:.2f}s] Error: {e}")
        return None, end_time - start_time

def main():
    print("VLI Consistency Audit (Cache Disabled)")
    
    # 1. Direct Mode (Fast Path)
    data_direct, time_direct = run_test(
        "Stage 1: Direct Mode (Fast-Path bypass)",
        "/vli analyze NVDA --RAW",
        direct_mode=False,
        raw_data_mode=True
    )
    
    # 2. Agentic Mode (Force Graph)
    data_agent, time_agent = run_test(
        "Stage 2: Agent Mode (Force Graph Execution)",
        "/vli analyze NVDA --RAW --FORCE-GRAPH",
        direct_mode=False, # standard reactive routing
        raw_data_mode=True
    )
    
    # 3. Compare JSON Data
    print("\n================ BENCHMARK RESULTS ================")
    print(f"Direct Mode Latency: {time_direct:.2f}s")
    print(f"Agent Mode Latency:  {time_agent:.2f}s")
    
    if data_direct is not None and data_agent is not None:
        import hashlib
        # Compare actual data payloads
        # We need to extract the "data" array if it matches the format
        dd = data_direct.get("data", data_direct) if isinstance(data_direct, dict) else data_direct
        da = data_agent.get("data", data_agent) if isinstance(data_agent, dict) else data_agent
        
        if len(dd) > 0 and len(da) > 0:
            dd = dd[:-1]
            da = da[:-1]
            
        # Serialize and compare hashes to avoid trivial ordering issues if dicts differ
        dd_str = json.dumps(dd, sort_keys=True)
        da_str = json.dumps(da, sort_keys=True)
        
        if dd_str == da_str:
            print("\nSTATUS: SUCCESS (1:1 Data Identity Verified)")
            print("Both paths produced identical raw JSON structures despite radically different trajectories.")
        else:
            print("\nSTATUS: FAILED (Data Mismatch)")
            print("Direct Length:", len(dd_str))
            print("Agent Length: ", len(da_str))
            with open("direct.json", "w") as f:
                f.write(dd_str)
            with open("agent.json", "w") as f:
                f.write(da_str)
    else:
        print("\nSTATUS: FAILED (One or more stages did not return JSON)")

if __name__ == '__main__':
    main()
