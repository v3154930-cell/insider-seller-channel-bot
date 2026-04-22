import requests, json, time

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

cat_id = 17028959
type_id = 96560

# Get required attrs
resp = requests.post("https://api-seller.ozon.ru/v1/description-category/attribute",
                     headers=HEADERS,
                     json={"description_category_id": cat_id, "type_id": type_id},
                     timeout=30)
attrs = resp.json().get("result", [])
required = [a for a in attrs if a.get("is_required")]
print(f"Required attrs: {len(required)}")
for a in required:
    print(f"  id={a['id']} name={a['name']} type={a['type']}")

attributes = [{"id": a["id"], "values": [{"value": "test"}]} for a in required]

product = {
    "offer_id": f"manual_{cat_id}_{type_id}",
    "name": "Manual Test",
    "description": "Test",
    "category_id": cat_id,
    "type_id": type_id,
    "price": "1000",
    "vat": "0.1",
    "images": ["https://img.freepik.com/free-photo/white-product_53876-66988.jpg"],
    "attributes": attributes
}

print(f"\nSending product with {len(attributes)} attributes...")
resp = requests.post("https://api-seller.ozon.ru/v3/product/import",
                     headers=HEADERS,
                     json={"items": [product]},
                     timeout=30)
data = resp.json()
task_id = data.get("result", {}).get("task_id")
print(f"Task ID: {task_id}")

if task_id:
    # Wait for import
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
                print("Imported! Getting commission...")
                offer_id = items[0].get("offer_id")
                resp3 = requests.post("https://api-seller.ozon.ru/v3/product/info/list",
                                      headers=HEADERS,
                                      json={"offer_id": [offer_id]},
                                      timeout=30)
                items3 = resp3.json().get("items", [])
                if items3:
                    commissions = items3[0].get("commissions", [])
                    print(f"Commissions: {commissions}")
                break
            elif status == "failed":
                errors = items[0].get("errors", [])
                print(f"Failed: {json.dumps(errors, ensure_ascii=False)[:500]}")
                break
    else:
        print("Timeout")
