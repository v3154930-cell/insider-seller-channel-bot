import requests
import json
import time

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

# Use leaf category from above
cat_id = 17028993
type_id = 970619133
cat_name = "����������� � ������"

# Get required attributes
resp = requests.post("https://api-seller.ozon.ru/v1/description-category/attribute",
                     headers=HEADERS,
                     json={"description_category_id": cat_id, "type_id": type_id},
                     timeout=30)
attrs = resp.json().get("result", [])
required = [a for a in attrs if a.get("is_required")]
print(f"Required attributes: {len(required)}")
for a in required:
    print(f"  id={a['id']} name={a['name']} type={a['type']}")

# Build product with required attrs
attributes = []
for attr in required:
    attr_id = attr.get("id")
    if attr_id:
        attributes.append({
            "id": attr_id,
            "values": [{"value": "test"}]
        })

offer_id = f"test_{cat_id}"
product = {
    "offer_id": offer_id,
    "name": "Test Product",
    "description": "Test",
    "category_id": cat_id,
    "type_id": type_id,
    "price": "1000",
    "vat": "0.1",
    "images": ["https://img.freepik.com/free-photo/white-product_53876-66988.jpg"],
    "attributes": attributes
}

resp = requests.post("https://api-seller.ozon.ru/v3/product/import",
                     headers=HEADERS,
                     json={"items": [product]},
                     timeout=30)
print(f"\nImport status: {resp.status_code}")
data = resp.json()
print(json.dumps(data, indent=2, ensure_ascii=False))
