#!/usr/bin/env python3
"""Test v5 with limit"""
import requests

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

h = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

url = "https://api-seller.ozon.ru/v5/product/info/prices"
payload = {"limit": 10}

resp = requests.post(url, headers=h, json=payload, timeout=15)
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    result = resp.json()
    items = result.get("result", {}).get("items", [])
    print(f"Items: {len(items)}")
    
    for item in items[:3]:
        comm = item.get("commissions", {})
        print(f"  offer_id: {item.get('offer_id')}")
        print(f"    commissions: {comm}")
else:
    print(f"Error: {resp.text[:200]}")