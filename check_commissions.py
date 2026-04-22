#!/usr/bin/env python3
import sqlite3
conn = sqlite3.connect('D:/LLM code/insider-seller-channel-bot/commissions.db')
c = conn.execute('SELECT marketplace, category, commission FROM commissions_history WHERE marketplace="ozon"')
print("Ozon commissions:")
for row in c:
    print(f"  {row[1]}: {row[2]}%")