import subprocess
import json
import sys

p = subprocess.run([sys.executable, 'scripts/call_vli.py', 'Get raw SMC data for ITA'], capture_output=True, text=True)
text = p.stdout
try:
    idx = text.find('{"ticker"')
    if idx != -1:
        raw = text[idx:]
        print(json.dumps(json.loads(raw), indent=2))
    else:
        print("COULD NOT FIND JSON: " + text)
except Exception as e:
    print(f"ERROR: {e}")
    print(text)
