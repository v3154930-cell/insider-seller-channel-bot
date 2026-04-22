import requests

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

cat_id = 200001485  # Stamps category
type_id = 971445088

resp = requests.post("https://api-seller.ozon.ru/v1/description-category/attribute",
                     headers=HEADERS,
                     json={"description_category_id": cat_id, "type_id": type_id},
                     timeout=30)
attrs = resp.json().get("result", [])

print("Attributes with dictionary_id:")
for a in attrs:
    if a.get("dictionary_id"):
        print(f"  id={a['id']} name={a['name']} dict_id={a['dictionary_id']} required={a['is_required']} type={a['type']}")
