import requests

CLIENT_ID = "4954"
API_KEY = "62af09cd-5c5e-4fa8-8764-11ce47abdbfc"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

resp = requests.post("https://api-seller.ozon.ru/v1/description-category/tree",
                     headers=HEADERS, json={}, timeout=30)
print("Status code:", resp.status_code)
print("Response:", resp.text[:500])
