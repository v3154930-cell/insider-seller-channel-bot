import requests

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

# Try with parent category and leaf type for "Сандалии"
cat_id = 15621048   # "Повседневная обувь" subcategory (parent of type)
type_id = 91264     # "Сандалии" type

required_attrs = [
    {"id": 85, "values": [{"value": "test"}]},       # name
    {"id": 5019, "values": [{"value": "1"}]},        # some int
    {"id": 8229, "values": [{"value": "test"}]},      # string
    {"id": 9048, "values": [{"value": "test"}]},      # another string
]

product = {
    "offer_id": "test_sandal",
    "name": "Sandals Test",
    "description": "Test product for sandals",
    "category_id": cat_id,
    "type_id": type_id,
    "price": "1000",
    "vat": "0.1",
    "images": ["https://img.freepik.com/free-photo/white-product_53876-66988.jpg"],
    "attributes": required_attrs
}

resp = requests.post("https://api-seller.ozon.ru/v3/product/import",
                     headers=HEADERS,
                     json={"items": [product]},
                     timeout=30)
print(f"Status: {resp.status_code}")
print(resp.text[:2000])
