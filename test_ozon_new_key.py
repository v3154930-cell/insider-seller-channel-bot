#!/usr/bin/env python3
"""Test new Ozon API key"""
import requests

CLIENT_ID = "2548826"  # Try with old first
API_KEY = "91361e9f-b270-466c-a984-fb11da4a94e1"

headers = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

endpoints = [
    ("POST", "/v1/description-category/tree", {"Content-Length": "0"}),
    ("POST", "/v2/product/list", {"filter": {}, "limit": 1}),
    ("POST", "/v1/commission/product", {"category_id": 17036179, "price": 1000, "sale_schema": "FBS"}),
    ("POST", "/v1/commission/offer", {"offer_id": "test", "price": 1000}),
    ("GET", "/v1/product/classes", None),
]

print(f"Testing API key: {API_KEY[:20]}...")
print(f"Client ID (test): {CLIENT_ID}")
print()

for method, path, payload in endpoints:
    url = f"https://api-seller.ozon.ru{path}"
    h = headers.copy()
    if method == "POST" and payload == {"Content-Length": "0"}:
        h["Content-Length"] = "0"
        payload = None
    try:
        if method == "POST":
            resp = requests.post(url, headers=h, json=payload, timeout=15)
        else:
            resp = requests.get(url, headers=h, timeout=15)
        print(f"{path}: {resp.status_code}")
    except Exception as e:
        print(f"{path}: ERROR {e}")