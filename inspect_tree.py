import requests
import json

CLIENT_ID = "4954"
API_KEY = "62af09cd-5c5e-4fa8-8764-11ce47abdbfc"

HEADERS = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

resp = requests.post("https://api-seller.ozon.ru/v1/description-category/tree",
                     headers=HEADERS, json={}, timeout=30)
data = resp.json()

print("Response keys:", list(data.keys()))
print("Full response:")
print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])
