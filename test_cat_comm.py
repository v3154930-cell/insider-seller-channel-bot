#!/usr/bin/env python3
"""Get all categories and test commission on a few"""
import requests

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

h = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

# Get categories
print("1. Getting category tree...")
resp = requests.post("https://api-seller.ozon.ru/v1/description-category/tree", 
    headers={**h, "Content-Length": "0"}, json={}, timeout=15)
cats = resp.json().get("result", [])
print(f"  Categories: {len(cats)}")

# Test first 5 categories with commission/product
print("\n2. Testing commission for categories...")
endpoints_to_try = [
    "/v1/commission/product",
    "/v1/commission/calculation",
    "/v1/commission/offer",
]

for ep in endpoints_to_try:
    url = f"https://api-seller.ozon.ru{ep}"
    payload = {"category_id": 17028760, "price": "1000", "sale_schema": "FBS"}
    resp = requests.post(url, headers=h, json=payload, timeout=10)
    print(f"  {ep}: {resp.status_code}")