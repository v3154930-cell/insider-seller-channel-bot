import requests, json, time

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

# Test all three category combos: working (17027953+96782) and failing (17028959+96560, 200001485+971445088)
tests = [
    (17027953, 96782, "Working earlier? (Automotive accessories)"),
    (17028959, 96560, "Failing (Adult toys)"),
    (200001485, 971445088, "Failing (Stamps?)"),
]

for cat_id, type_id, label in tests:
    resp = requests.post("https://api-seller.ozon.ru/v1/description-category/attribute",
                         headers=HEADERS,
                         json={"description_category_id": cat_id, "type_id": type_id},
                         timeout=30)
    attrs = resp.json().get("result", [])
    required = [a for a in attrs if a.get("is_required")]
    attributes = [{"id": a["id"], "values": [{"value": "test"}]} for a in required]

    product = {
        "offer_id": f"test_{cat_id}_{type_id}",
        "name": "Test Prod",
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
    data = resp.json()
    task_id = data.get("result", {}).get("task_id")
    print(f"\n{label}: task_id={task_id}")

    if task_id:
        # Wait 50s for import
        for i in range(25):
            time.sleep(2)
            resp2 = requests.post("https://api-seller.ozon.ru/v1/product/import/info",
                                  headers=HEADERS,
                                  json={"task_id": task_id},
                                  timeout=30)
            items = resp2.json().get("result", {}).get("items", [])
            if items:
                status = items[0].get("status")
                if status == "imported":
                    print(f"  Imported! offer_id={items[0].get('offer_id')}")
                    # Get commission
                    resp3 = requests.post("https://api-seller.ozon.ru/v3/product/info/list",
                                          headers=HEADERS,
                                          json={"offer_id": [items[0].get('offer_id')]},
                                          timeout=30)
                    items3 = resp3.json().get("items", [])
                    if items3:
                        comm = items3[0].get("commissions", [])
                        print(f"  Commission: {comm}")
                    break
                elif status == "failed":
                    errors = items[0].get("errors", [])
                    print(f"  Failed: {errors[0].get('code') if errors else 'unknown'}")
                    break
        else:
            print("  Timeout waiting")
