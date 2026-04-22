import requests
import json

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

resp = requests.post("https://api-seller.ozon.ru/v1/description-category/tree",
                     headers=HEADERS, json={}, timeout=30)
data = resp.json()

with open("ozon_tree_dump.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Tree saved to ozon_tree_dump.json")

# Find categories with type_id at any level
categories_with_type = []

def traverse(node, path=[]):
    current_path = path + [node.get("category_name", "?")]
    children = node.get("children", [])
    node_type_id = node.get("type_id")

    if node_type_id:
        categories_with_type.append({
            "path": " > ".join(current_path),
            "description_category_id": node.get("description_category_id"),
            "type_id": node_type_id,
            "category_name": node.get("category_name")
        })

    for child in children:
        traverse(child, current_path)

for root in data.get("result", []):
    traverse(root)

print(f"\nNodes with type_id: {len(categories_with_type)}")
for c in categories_with_type[:10]:
    print(f"  type_id={c['type_id']} cat_id={c['description_category_id']} name={c['category_name']}")
