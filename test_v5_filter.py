#!/usr/bin/env python3
"""Test v5 with valid filter"""
import requests

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

h = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

# Try with offer_id filter
url = "https://api-seller.ozon.ru/v5/product/info/prices"

# First get offer IDs from product list
resp = requests.post("https://api-seller.ozon.ru/v3/product/list", 
    headers=h, json={"filter": {"is_archive": False}, "limit": 5})
items = resp.json().get("result", {}).get("items", [])
offer_ids = [i.get("offer_id") for i in items]
print(f"Offer IDs: {offer_ids}")

# Try with offer_id in filter
payload = {"filter": {"offer_id": offer_ids[0]}, "limit": 10}
print(f"\nTrying filter offer_id: {payload}")
resp = requests.post(url, headers=h, json=payload, timeout=15)
print(f"Status: {resp.status_code}, Response: {resp.text[:200]}")

# Try with product_id in filter
pid = items[0].get("product_id")
payload = {"filter": {"product_id": pid}, "limit": 10}
print(f"\nTrying filter product_id: {payload}")
resp = requests.post(url, headers=h, json=payload, timeout=15)
print(f"Status: {resp.status_code}, Response: {resp.text[:200]}")