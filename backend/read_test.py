import traceback
try:
    with open('test_out.txt', 'r', encoding='utf-16le') as f:
        lines = f.readlines()
        print(''.join(lines[-50:]))
except Exception as e:
    print('Failed:', e)
