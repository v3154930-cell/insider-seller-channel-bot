#!/usr/bin/env python3
import requests

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

headers = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

# Test commission/calculation
url = "https://api-seller.ozon.ru/v1/commission/calculation"
payload = {
    "category_id": 17028760,  # Automotive oils
    "price": "1000"
}

print("Testing /v1/commission/calculation...")
resp = requests.post(url, headers=headers, json=payload, timeout=15)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:300]}")