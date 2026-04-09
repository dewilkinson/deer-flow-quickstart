import csv

source = 'logs/Accounts_History (14).csv'
print("RAW CSV LINES CONTAINING 'GLDM' ON '04/09':")
with open(source, 'r', encoding='utf-8') as f:
    for line in f:
        if 'GLDM' in line and '04/09' in line:
            print(line.strip())
