source = 'logs/Accounts_History (14).csv'
print("ALL GLDM TRADES IN SOURCE:")
with open(source, 'r', encoding='utf-8') as f:
    for line in f:
        if 'GLDM' in line:
            print(line.strip())
