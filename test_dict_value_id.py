import requests, json, time

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

cat_id = 17028959
type_id = 96560

# Get attributes
resp = requests.post("https://api-seller.ozon.ru/v1/description-category/attribute",
                     headers=HEADERS,
                     json={"description_category_id": cat_id, "type_id": type_id},
                     timeout=30)
attrs = resp.json().get("result", [])
required = [a for a in attrs if a.get("is_required")]
print(f"Required attrs count: {len(required)}")

# Build attributes: for dictionary attrs, fetch value_id; for others use test value
attributes = []
dict_cache = {}

for attr in required:
    attr_id = attr.get("id")
    dict_id = attr.get("dictionary_id")
    if dict_id:
        # Fetch dictionary values for this attribute
        respd = requests.post("https://api-seller.ozon.ru/v1/description-category/attribute/values",
                              headers=HEADERS,
                              json={"attribute_id": attr_id, "description_category_id": cat_id, "type_id": type_id, "limit": 1},
                              timeout=30)
        vals = respd.json().get("result", [])
        if vals:
            val = vals[0]
            attributes.append({"id": attr_id, "value_id": val["id"]})
            dict_cache[attr_id] = val
        else:
            # fallback
            attributes.append({"id": attr_id, "values": [{"value": "test"}]})
    else:
        # Non-dictionary: use a default based on type
        attr_type = attr.get("type", "string").lower()
        if attr_type == "integer":
            attributes.append({"id": attr_id, "values": [{"value": "1"}]})
        elif attr_type == "decimal":
            attributes.append({"id": attr_id, "values": [{"value": "1.0"}]})
        else:
            attributes.append({"id": attr_id, "values": [{"value": "test"}]})

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

print(f"Sending product with {len(attributes)} attrs")
resp = requests.post("https://api-seller.ozon.ru/v3/product/import",
                     headers=HEADERS,
                     json={"items": [product]},
                     timeout=30)
data = resp.json()
task_id = data.get("result", {}).get("task_id")
print(f"Task: {task_id}")

if task_id:
    for i in range(25):
        time.sleep(2)
        resp2 = requests.post("https://api-seller.ozon.ru/v1/product/import/info",
                              headers=HEADERS,
                              json={"task_id": task_id},
                              timeout=30)
        items = resp2.json().get("result", {}).get("items", [])
        if items:
            status = items[0].get("status")
            print(f"[{i}] Status: {status}")
            if status == "imported":
                print("Success!")
                break
            elif status == "failed":
                print(f"Errors: {items[0].get('errors')}")
                break
    else:
        print("Timeout")
