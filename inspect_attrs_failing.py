import requests

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

cat_id = 17028959
type_id = 96560

resp = requests.post("https://api-seller.ozon.ru/v1/description-category/attribute",
                     headers=HEADERS,
                     json={"description_category_id": cat_id, "type_id": type_id},
                     timeout=30)
attrs = resp.json().get("result", [])

print("All attributes:")
for a in attrs:
    print(f"  id={a['id']} type={a['type']:12} required={a['is_required']} name={a['name']}")
