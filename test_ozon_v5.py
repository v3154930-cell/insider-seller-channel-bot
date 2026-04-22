#!/usr/bin/env python3
import requests

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

headers = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

print("=== Testing new Ozon key ===")
print(f"Client ID: {CLIENT_ID}")
print(f"API Key: {API_KEY[:25]}...")
print()

# Test 1: product list with filter
print("1. Testing /v3/product/list with filter...")
url = "https://api-seller.ozon.ru/v3/product/list"
# Try with empty filter first
payload = {"filter": {"is_archive": False}, "limit": 10}

resp = requests.post(url, headers=headers, json=payload)
print(f"   Status: {resp.status_code}")
if resp.status_code == 200:
    items = resp.json().get("result", {}).get("items", [])
    print(f"   Found products: {len(items)}")
    for item in items[:3]:
        print(f"     - product_id: {item.get('product_id')}, offer_id: {item.get('offer_id')}")
else:
    print(f"   Error: {resp.text[:200]}")
print()

# Test 2: product info prices - debug
print("2. Testing /v5/product/info/prices...")
url = "https://api-seller.ozon.ru/v5/product/info/prices"
payload = {"filter": {"visibility": "ALL"}, "limit": 100}

resp = requests.post(url, headers=headers, json=payload)
print(f"   Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    items = data.get("result", {}).get("items", [])
    print(f"   Found items: {len(items)}")
    
    # Show first item structure
    if items:
        print(f"   First item keys: {list(items[0].keys())}")
        print(f"   First item: {items[0]}")