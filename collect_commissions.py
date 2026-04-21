#!/usr/bin/env python3
"""
Собирает комиссии со всех товаров-зондов Ozon
Запускать 2 раза в сутки (6:00 и 22:00)
"""
import requests
import sqlite3
import json
from datetime import datetime

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

HEADERS = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

DB_PATH = "/opt/newsbot/data/ozon_commissions.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_id INTEGER,
            category_name TEXT,
            commission_fbs REAL,
            commission_fbo REAL,
            collected_at TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_type_id ON commissions(type_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_collected_at ON commissions(collected_at)
    """)
    conn.commit()
    conn.close()

def get_all_probes():
    """Получает все товары-зонды"""
    url = "https://api-seller.ozon.ru/v3/product/list"
    payload = {"filter": {"offer_id": ["probe_"]}, "limit": 1000}
    
    all_items = []
    while True:
        resp = requests.post(url, headers=HEADERS, json=payload)
        data = resp.json()
        items = data.get("result", {}).get("items", [])
        all_items.extend(items)
        
        if not data.get("result", {}).get("has_next"):
            break
        payload["last_id"] = data.get("result", {}).get("last_id")
    
    return all_items

def get_commission(product_id):
    """Получает комиссию для товара"""
    url = "https://api-seller.ozon.ru/v5/product/info/prices"
    payload = {"filter": {"product_id": [product_id]}, "limit": 1}
    
    resp = requests.post(url, headers=HEADERS, json=payload)
    items = resp.json().get("result", {}).get("items", [])
    
    for item in items:
        comm = item.get("commissions", {})
        fbs = comm.get("sales_percent_fbs")
        fbo = comm.get("sales_percent_fbo")
        return fbs, fbo
    return None, None

def save_commission(type_id, category_name, fbs, fbo):
    """Сохраняет комиссию в БД"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO commissions (type_id, category_name, commission_fbs, commission_fbo, collected_at)
        VALUES (?, ?, ?, ?, ?)
    """, (type_id, category_name, fbs, fbo, datetime.now()))
    conn.commit()
    conn.close()

def main():
    print(f"📊 Сбор комиссий Ozon — {datetime.now()}")
    init_db()
    
    # Загружаем type_id
    with open('/tmp/type_ids.json', 'r') as f:
        type_ids = json.load(f)
    
    # Создаём словарь type_id -> category_name
    type_to_category = {item['type_id']: item['name'] for item in type_ids}
    
    # Получаем все зонды
    probes = get_all_probes()
    print(f"✅ Найдено зондов: {len(probes)}")
    
    collected = 0
    for probe in probes:
        offer_id = probe.get("offer_id")
        product_id = probe.get("product_id")
        
        # Извлекаем type_id из offer_id
        if offer_id and offer_id.startswith("probe_"):
            type_id = int(offer_id.replace("probe_", ""))
            category_name = type_to_category.get(type_id, "Unknown")
            
            fbs, fbo = get_commission(product_id)
            if fbs or fbo:
                save_commission(type_id, category_name, fbs, fbo)
                collected += 1
                print(f"  {category_name[:40]}: FBS={fbs}%, FBO={fbo}%")
    
    print(f"✅ Собрано комиссий: {collected}")

if __name__ == "__main__":
    main()
