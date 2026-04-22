import requests

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

cat_id = 17027953
type_id = 96782

# Get attributes for this combo
resp = requests.post("https://api-seller.ozon.ru/v1/description-category/attribute",
                     headers=HEADERS,
                     json={"description_category_id": cat_id, "type_id": type_id},
                     timeout=30)
print(f"Attrs status: {resp.status_code}")
attrs = resp.json().get("result", [])
required = [a for a in attrs if a.get("is_required")]
print(f"Required attrs count: {len(required)}")

# Build minimal product
attributes = [{"id": a["id"], "values": [{"value": "test"}]} for a in required]

product = {
    "offer_id": f"test_{cat_id}_{type_id}",
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
print(resp.text[:1000])
