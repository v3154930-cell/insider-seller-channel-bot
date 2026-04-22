#!/usr/bin/env python3
"""Fresh test - wait and retry v5"""
import time
import requests

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

h = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

print("Waiting 2 seconds...")
time.sleep(2)

print("\nCalling v5/product/info/prices...")
url = "https://api-seller.ozon.ru/v5/product/info/prices"
payload = {"filter": {"visibility": "ALL"}, "limit": 10}

resp = requests.post(url, headers=h, json=payload, timeout=15)
print(f"Status: {resp.status_code}")

if resp.status_code == 200:
    result = resp.json()
    items = result.get("result", {}).get("items", [])
    print(f"Items: {len(items)}")
    if items:
        for item in items[:3]:
            print(f"  {item.get('offer_id')}: {item.get('commissions', {}).get('sales_percent_fbs')}")
    else:
        print(f"Response: {resp.text[:300]}")