import requests

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"

headers = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

url = "https://api-seller.ozon.ru/v1/description-category/tree"
resp = requests.post(url, headers=headers, json={}, timeout=30)

print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    categories = data.get("result", [])
    print(f"OK Categories received: {len(categories)}")
    if categories:
        print(f"First category: {categories[0].get('category_name')}")
else:
    print(f"Error: {resp.text[:500]}")
