#!/usr/bin/env python3
"""Check response structure"""
import requests

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

h = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

url = "https://api-seller.ozon.ru/v5/product/info/prices"
payload = {"filter": {"visibility": "ALL"}, "limit": 10}

resp = requests.post(url, headers=h, json=payload, timeout=15)
print(f"Status: {resp.status_code}")

result = resp.json()
print(f"Keys in result: {list(result.keys())}")
print(f"Result type: {type(result)}")

items = result.get("items", [])
print(f"Items from result.get: {len(items)}")

# Check if it's nested or different structure
if "result" in result:
    print(f"result key: {type(result['result'])}")
    inner = result['result']
    if isinstance(inner, dict):
        print(f"  inner keys: {list(inner.keys())}")
        items2 = inner.get("items", [])
        print(f"  items from inner: {len(items2)}")