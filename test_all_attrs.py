import requests, json, time

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

cat_id = 17028959
type_id = 96560

# Get ALL attributes, not just required
resp = requests.post("https://api-seller.ozon.ru/v1/description-category/attribute",
                     headers=HEADERS,
                     json={"description_category_id": cat_id, "type_id": type_id},
                     timeout=30)
all_attrs = resp.json().get("result", [])
print(f"Total attrs: {len(all_attrs)}")
print(f"Required: {len([a for a in all_attrs if a.get('is_required')])}")
print(f"Optional: {len([a for a in all_attrs if not a.get('is_required')])}")

# Try sending all attributes, not just required
attributes = []
for attr in all_attrs:
    attr_id = attr.get("id")
    if attr_id:
        attributes.append({
            "id": attr_id,
            "values": [{"value": "test"}]
        })

product = {
    "offer_id": f"allattrs_{cat_id}_{type_id}",
    "name": "All Attrs Test",
    "description": "Test",
    "category_id": cat_id,
    "type_id": type_id,
    "price": "1000",
    "vat": "0.1",
    "images": ["https://img.freepik.com/free-photo/white-product_53876-66988.jpg"],
    "attributes": attributes
}

print(f"Sending with {len(attributes)} attributes...")
resp = requests.post("https://api-seller.ozon.ru/v3/product/import",
                     headers=HEADERS,
                     json={"items": [product]},
                     timeout=30)
data = resp.json()
task_id = data.get("result", {}).get("task_id")
print(f"Task: {task_id}")

if task_id:
    time.sleep(45)
    resp2 = requests.post("https://api-seller.ozon.ru/v1/product/import/info",
                          headers=HEADERS,
                          json={"task_id": task_id},
                          timeout=30)
    items = resp2.json().get("result", {}).get("items", [])
    if items:
        print(f"Status: {items[0].get('status')}")
        print(f"Errors: {items[0].get('errors', [])}")
