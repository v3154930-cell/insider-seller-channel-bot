import requests
import json
import time

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

task_id = 4243362173

# Wait for import
for i in range(25):
    resp = requests.post("https://api-seller.ozon.ru/v1/product/import/info",
                         headers=HEADERS,
                         json={"task_id": task_id},
                         timeout=30)
    items = resp.json().get("result", {}).get("items", [])
    if items:
        status = items[0].get("status")
        offer_id = items[0].get("offer_id")
        print(f"[{i}] Status: {status}, offer_id: {offer_id}")
        if status == "imported":
            print("Import complete!")
            # Get commission
            resp2 = requests.post("https://api-seller.ozon.ru/v3/product/info/list",
                                  headers=HEADERS,
                                  json={"offer_id": [offer_id]},
                                  timeout=30)
            items2 = resp2.json().get("items", [])
            if items2:
                commissions = items2[0].get("commissions", [])
                print(f"Commissions: {commissions}")
            break
        elif status == "failed":
            print(f"Failed: {items[0].get('errors')}")
            break
    time.sleep(2)
else:
    print("Timeout waiting for import")
