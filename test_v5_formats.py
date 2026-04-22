#!/usr/bin/env python3
"""Test v5 with correct filter format"""
import requests

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

h = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

url = "https://api-seller.ozon.ru/v5/product/info/prices"

# Try various filter structures
filters_to_try = [
    {"visibility": "ALL"},
    {"is_archive": False},
    {},
    {"offer_id": ["test"]},
    {"product_id": [1354074670]},
]

for f in filters_to_try:
    payload = {"filter": f, "limit": 10}
    print(f"Filter: {f}")
    try:
        resp = requests.post(url, headers=h, json=payload, timeout=15)
        print(f"  {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"  Error: {e}")