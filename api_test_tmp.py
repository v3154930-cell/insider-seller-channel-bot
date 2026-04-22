#!/usr/bin/env python3
import requests
import json
import os
import tempfile

CLIENT_ID = "4954"
API_KEY = "62af09cd-5c5e-4fa8-8764-11ce47abdbfc"

HEADERS = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

# Use temp directory
tmpdir = tempfile.gettempdir()
output_path = os.path.join(tmpdir, "ozon_api_test.json")

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
        # Show up to 3 categories
        result["sample_categories"] = [
            {"name": c.get("category_name"), "id": c.get("description_category_id")}
            for c in categories[:3]
        ]

except Exception as e:
    result["status"] = "failed"
    result["error"] = str(e)
    import traceback
    result["traceback"] = traceback.format_exc()

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"Results saved to: {output_path}")
print(json.dumps(result, indent=2, ensure_ascii=False))
