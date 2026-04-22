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

result = {"status": "running", "categories": [], "error": None}

try:
    resp = requests.post(
        "https://api-seller.ozon.ru/v1/description-category/tree",
        headers=HEADERS, json={}, timeout=30
    )
    result["status_code"] = resp.status_code
    data = resp.json()
    categories = data.get("result", [])
    result["categories_count"] = len(categories)
    result["status"] = "success"

    if categories:
        first = categories[0]
        result["first_category"] = {
            "name": first.get("category_name"),
            "id": first.get("description_category_id"),
            "children_count": len(first.get("children", []))
        }

except Exception as e:
    result["status"] = "failed"
    result["error"] = str(e)

with open("api_test_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print("Test complete. See api_test_result.json")
