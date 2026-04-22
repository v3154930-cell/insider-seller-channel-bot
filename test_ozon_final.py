#!/usr/bin/env python3
"""Test both Ozon keys with Client ID 2548826"""
import requests
import json

CLIENT_ID = "2548826"

keys_to_test = [
    ("9f9b3abe-49ae-4f7d-99ad-5211434a8ff8", "old key from task"),
    ("91361e9f-b270-466c-a984-fb11da4a94e1", "new key"),
]

for API_KEY, desc in keys_to_test:
    print(f"=== Testing {desc} ===")
    print(f"API Key: {API_KEY[:25]}...")
    
    headers = {
        "Client-Id": CLIENT_ID,
        "Api-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    # Test 1: category tree
    url = "https://api-seller.ozon.ru/v1/description-category/tree"
    resp = requests.post(url, headers={**headers, "Content-Length": "0"}, timeout=15)
    print(f"  /v1/description-category/tree: {resp.status_code}")
    
    # Test 2: product list
    url = "https://api-seller.ozon.ru/v2/product/list"
    resp = requests.post(url, headers=headers, json={"filter": {}, "limit": 1}, timeout=15)
    print(f"  /v2/product/list: {resp.status_code} {resp.text[:100] if resp.status_code == 404 else ''}")
    
    # Test 3: commission product
    url = "https://api-seller.ozon.ru/v1/commission/product"
    resp = requests.post(url, headers=headers, json={"category_id": 17036179, "price": 1000, "sale_schema": "FBS"}, timeout=15)
    print(f"  /v1/commission/product: {resp.status_code} {resp.text[:100] if resp.status_code == 404 else ''}")
    
    print()