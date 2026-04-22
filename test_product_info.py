#!/usr/bin/env python3
import requests

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

headers = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

# Get list first
url = "https://api-seller.ozon.ru/v3/product/list"
payload = {"filter": {"is_archive": False}, "limit": 5}

resp = requests.post(url, headers=headers, json=payload)
items = resp.json().get("result", {}).get("items", [])
product_ids = [item.get("product_id") for item in items]
print(f"Products: {product_ids}")

# Try v1/product/info
print("\nTrying v1/product/info...")
for pid in product_ids[:2]:
    url = "https://api-seller.ozon.ru/v1/product/info"
    payload = {"product_id": pid}
    
    resp = requests.post(url, headers=headers, json=payload)
    print(f"  v1/product/info {pid}: {resp.status_code}")
    if resp.status_code == 200:
        print(f"    {resp.text[:200]}")
    else:
        print(f"    {resp.text[:100]}")

# Try v1/product/list (without filter)
print("\nTrying v1/product/list...")
url = "https://api-seller.ozon.ru/v1/product/list"
payload = {"limit": 5}

resp = requests.post(url, headers=headers, json=payload)
print(f"  v1/product/list: {resp.status_code}")
if resp.status_code == 200:
    print(f"    {resp.text[:200]}")
else:
    print(f"    {resp.text[:100]}")