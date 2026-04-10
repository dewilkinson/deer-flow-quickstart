import os

filepath = 'src/tools/finance.py'
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix UnboundLocalError by hoisting initialization of m_struct_detail
text = text.replace('mDF = mData_res.tail(macro_lookback).copy()\n        if not mDF.empty:',
                    'mDF = mData_res.tail(macro_lookback).copy()\n        m_struct_detail = ""\n        if not mDF.empty:')

text = text.replace('            # Simple bias heuristic based on the latest structural event\n            m_struct_detail = ""\n',
                    '            # Simple bias heuristic based on the latest structural event\n')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print("Replacement complete.")
