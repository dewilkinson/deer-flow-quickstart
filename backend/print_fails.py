import json
with open('report.json', encoding='utf-8') as f: data = json.load(f)
for t in data.get('tests', []):
 if t.get('outcome') == 'failed': print(t['nodeid'], t.get('call', {}).get('crash', {}).get('message'))
