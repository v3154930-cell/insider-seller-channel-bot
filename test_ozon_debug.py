#!/usr/bin/env python3
import requests

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

headers = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

# Get list of product IDs first
print("1. Getting product list...")
url = "https://api-seller.ozon.ru/v3/product/list"
payload = {"filter": {"is_archive": False}, "limit": 50}

resp = requests.post(url, headers=headers, json=payload)
items = resp.json().get("result", {}).get("items", [])
product_ids = [item.get("product_id") for item in items if item.get("product_id")]
print(f"   Found {len(product_ids)} product IDs: {product_ids[:5]}")

# Try getting info for specific products
print("\n2. Getting product details...")
for pid in product_ids[:3]:
    url = "https://api-seller.ozon.ru/v2/product/info"
    payload = {"product_id": pid}
    
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 200:
        result = resp.json().get("result", {})
        print(f"   Product {pid}:")
        print(f"     keys: {list(result.keys())}")
        
        # Check for commissions
        comms = result.get("commissions", [])
        if comms:
            for c in comms:
                print(f"     commission: {c}")
        else:
            print(f"     commissions: {comms}")
        
        # Check for category
        cat = result.get("category_id") or result.get("category_title")
        print(f"     category: {cat}")
    else:
        print(f"   Product {pid}: {resp.status_code} {resp.text[:100]}")