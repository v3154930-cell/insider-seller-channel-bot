import requests

CLIENT_ID = "4954"
API_KEY = "62af09cd-5c5e-4fa8-8764-11ce47abdbfc"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

# Test product import endpoint
resp = requests.post("https://api-seller.ozon.ru/v3/product/import",
                     headers=HEADERS, json={"items": []}, timeout=30)
print("Product import status:", resp.status_code)
print("Response:", resp.text[:500])
