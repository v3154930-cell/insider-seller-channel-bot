import requests

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"
HEADERS = {"Client-Id": CLIENT_ID, "Api-Key": API_KEY, "Content-Type": "application/json"}

for (cat_id, type_id, label) in [(17027953,96782,"Working?"),(17028959,96560,"Failing")]:
    resp = requests.post("https://api-seller.ozon.ru/v1/description-category/attribute",
                         headers=HEADERS,
                         json={"description_category_id": cat_id, "type_id": type_id},
                         timeout=30)
    attrs = resp.json().get("result", [])
    required = [a for a in attrs if a.get("is_required")]
    with_dict = [a for a in required if a.get("dictionary_id")]
    print(f"{label}: required={len(required)} with_dict={len(with_dict)}")
    for a in with_dict:
        print(f"  id={a['id']} name={a['name']} dict_id={a['dictionary_id']}")
