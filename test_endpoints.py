#!/usr/bin/env python3
"""Find working Ozon API endpoints"""
import requests

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

# Get product IDs first
h = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}
resp = requests.post("https://api-seller.ozon.ru/v3/product/list", 
    headers=h, json={"filter": {"is_archive": False}, "limit": 5})
pids = [i["product_id"] for i in resp.json().get("result", {}).get("items", [])]
print(f"Product IDs: {pids}")

# Try various endpoints with first product ID
endpoints = [
    ("POST", "/v2/product/info", {"product_id": pids[0]}),
    ("POST", "/v1/product/info", {"product_id": pids[0]}),
    ("POST", "/v1/product/info/attributes", {"product_id": pids[0]}),
    ("POST", "/v2/product/info/attributes", {"product_id": pids[0]}),
    ("POST", "/v1/card", {"product_id": pids[0]}),
    ("POST", "/v2/card", {"product_id": pids[0]}),
]

for method, path, payload in endpoints:
    try:
        if method == "POST":
            resp = requests.post(f"https://api-seller.ozon.ru{path}", headers=h, json=payload, timeout=10)
        print(f"{path}: {resp.status_code}")
    except Exception as e:
        print(f"{path}: ERROR {e}")