import requests
import json

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

resp = requests.post("https://api-seller.ozon.ru/v1/description-category/tree",
                     headers=HEADERS, json={}, timeout=30)
data = resp.json()

categories = data.get("result", [])
print(f"Root categories: {len(categories)}")

# Find categories with type_id (leaf nodes)
leaf_cats = []

def traverse(cats, depth=0):
    for cat in cats:
        cat_id = cat.get("description_category_id")
        cat_name = cat.get("category_name")
        children = cat.get("children", [])
        type_id = None

        # Check if any child has type_id
        for child in children:
            if child.get("type_id"):
                type_id = child.get("type_id")
                break

        if type_id:
            leaf_cats.append({
                "id": cat_id,
                "name": cat_name,
                "type_id": type_id
            })

        if children:
            traverse(children, depth+1)

traverse(categories)
print(f"Leaf categories with type_id: {len(leaf_cats)}")
if leaf_cats:
    print("\nFirst 5 leaf categories:")
    for c in leaf_cats[:5]:
        print(f"  ID={c['id']} type_id={c['type_id']} name={c['name']}")
