#!/usr/bin/env python3
import requests
import json

CLIENT_ID = "4954"
API_KEY = "62af09cd-5c5e-4fa8-8764-11ce47abdbfc"

HEADERS = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

# Test 1: Get categories tree
print("Testing Ozon API connectivity...")
try:
    resp = requests.post("https://api-seller.ozon.ru/v1/description-category/tree",
                        headers=HEADERS, json={}, timeout=30)
    data = resp.json()
    categories = data.get("result", [])
    print(f"✅ API connection OK. Root categories: {len(categories)}")
    print(f"Full response keys: {list(data.keys())}")

    # Show first category
    if categories:
        first = categories[0]
        print(f"First category: {first.get('category_name')} (ID: {first.get('description_category_id')})")
        print(f"Children count: {len(first.get('children', []))}")
except Exception as e:
    print(f"❌ API Error: {e}")
    import traceback
    traceback.print_exc()
