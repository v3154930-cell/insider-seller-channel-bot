import requests

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

# Use first leaf category
cat_id = 17028993
type_id = 970619133

# Get attributes
resp = requests.post("https://api-seller.ozon.ru/v1/description-category/attribute",
                     headers=HEADERS,
                     json={"description_category_id": cat_id, "type_id": type_id},
                     timeout=30)
print(f"Attribute status: {resp.status_code}")
print(resp.text[:2000])
