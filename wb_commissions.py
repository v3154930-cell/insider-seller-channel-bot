#!/usr/bin/env python3
"""
Сборщик комиссий Wildberries с автоматическими повторами при 429
"""
import requests
import sqlite3
import os
import time
from datetime import datetime

WB_API_KEY = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjYwMzAydjEiLCJ0eXAiOiJKV1QifQ.eyJhY2MiOjEsImVudCI6MSwiZXhwIjoxNzkyNTM2NjQxLCJpZCI6IjAxOWRhZmE5LWViNzYtNzYzNS1hNzE2LWQwYTEyOTVmMWJjYSIsImlpZCI6NDQwNTYzNzEsIm9pZCI6MjUwMTA1MjUyLCJzIjoxMDczNzU3MzEwLCJzaWQiOiIyOTc1ZGFlMi04NjBmLTRhMDQtYjg0ZS0yN2JmNTg5ZTAzZGMiLCJ0IjpmYWxzZSwidWlkIjo0NDA1NjM3MX0.NWTl_wEwuqH_uk-eoGhbwYYEpyIbKK0jw37ELyb8qEKaoLUrTppzIF3A9Ga417HG6L914rUGt_Rjc7v-ApSa1w"

DB_PATH = "/opt/newsbot/data/wb_commissions.db"
os.makedirs("/opt/newsbot/data", exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            commission REAL,
            collected_at TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def collect_wb_with_retry(max_retries=5):
    """Собирает комиссии с повторами при 429"""
    headers = {"Authorization": f"Bearer {WB_API_KEY}"}
    url = "https://common-api.wildberries.ru/api/v1/tariffs/commission"
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                wait = (2 ** attempt) + 1  # 1, 3, 7, 15, 31 секунд
                print(f"  ⏳ Лимит запросов, ждём {wait} сек...")
                time.sleep(wait)
            else:
                print(f"  ❌ Ошибка {resp.status_code}: {resp.text[:100]}")
                return None
        except Exception as e:
            print(f"  ❌ Исключение: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    print("  ❌ Превышено количество попыток")
    return None

def main():
    print(f"📊 Сбор комиссий Wildberries — {datetime.now()}")
    init_db()
    
    data = collect_wb_with_retry()
    if not data:
        print("❌ Не удалось получить данные")
        return
    
    commissions = {}
    for item in data.get("report", []):
        category = item.get("subjectName")
        commission = item.get("kgvpMarketplace")
        if category and commission:
            commissions[category] = commission
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now()
    
    for category, rate in commissions.items():
        cursor.execute("""
            INSERT INTO commissions (category, commission, collected_at)
            VALUES (?, ?, ?)
        """, (category, rate, now))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Собрано комиссий: {len(commissions)}")
    print(f"💾 Сохранено в: {DB_PATH}")

if __name__ == "__main__":
    main()
