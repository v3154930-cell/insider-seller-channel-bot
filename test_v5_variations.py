#!/usr/bin/env python3
"""Test exact response from v5"""
import requests

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

h = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

# Test v5 with product_id filter
url = "https://api-seller.ozon.ru/v5/product/info/prices"
payloads = [
    {"filter": {"visibility": "ALL"}},
    {"filter": {}},
    {"product_id": 1354074670},
]

for i, payload in enumerate(payloads):
    print(f"\nPayload {i+1}: {payload}")
    resp = requests.post(url, headers=h, json=payload, timeout=15)
    print(f"  Status: {resp.status_code}, Response: {resp.text[:150]}")