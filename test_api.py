import requests

CLIENT_ID = '4140504'
API_KEY = '5a14cdc1-2557-45ed-8e30-47a6823931d1'

headers = {
    'Client-Id': CLIENT_ID,
    'Api-Key': API_KEY,
    'Content-Type': 'application/json'
}

def count_categories(categories, depth=0):
    count = 0
    for cat in categories:
        if cat.get('description_category_id') and cat.get('category_name'):
            count += 1
            print('  ' * depth + f'- {cat.get("category_name")} (ID: {cat.get("description_category_id")})')
        if cat.get('children'):
            count += count_categories(cat.get('children'), depth + 1)
    return count

url = 'https://api-seller.ozon.ru/v1/description-category/tree'
resp = requests.post(url, headers=headers, json={})
categories = resp.json().get('result', [])

print('TREE CATEGORIES:')
total = count_categories(categories)
print(f'Total categories (with nested): {total}')