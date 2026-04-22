#!/usr/bin/env python3
"""Test various Ozon API endpoints"""
import requests

CLIENT_ID = "2548826"
API_KEY = "9f9b3abe-49ae-4f7d-99ad-5211434a8ff8"

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