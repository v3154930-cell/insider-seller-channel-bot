import requests
import json

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

resp = requests.post("https://api-seller.ozon.ru/v1/description-category/tree",
                     headers=HEADERS, json={}, timeout=30)
data = resp.json()

flat = []

def traverse(cats):
    for cat in cats:
        cat_id = cat.get("description_category_id")
        cat_name = cat.get("category_name")
        children = cat.get("children", [])

        for child in children:
            if child.get("type_id"):
                flat.append({
                    "category_id": cat_id,
                    "type_id": child.get("type_id"),
                    "name": f"{cat_name} — {child.get('type_name', '')}"
                })

        if children:
            traverse(children)

traverse(data.get("result", []))

print(f"Total: {len(flat)}")
print("\nFirst 20:")
for i, item in enumerate(flat[:20], 1):
    print(f"{i:2}. cat_id={item['category_id']} type_id={item['type_id']} name={item['name']}")
