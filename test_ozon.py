#!/usr/bin/env python3
"""
Test Ozon API — obtaining commissions
"""
import requests
import json

CLIENT_ID = "2548826"
API_KEY = "9f9b3abe-49ae-4f7d-99ad-5211434a8ff8"

def get_categories():
    """Get category tree"""
    url = "https://api-seller.ozon.ru/v1/description-category/tree"
    headers = {
        "Client-Id": CLIENT_ID,
        "Api-Key": API_KEY,
        "Content-Type": "application/json",
        "Content-Length": "0"
    }
    resp = requests.post(url, headers=headers, timeout=30)
    return resp.json().get("result", [])

def get_commission_via_product(category_id):
    """Try to get commission via product/info"""
    url = "https://api-seller.ozon.ru/v2/product/list"
    headers = {
        "Client-Id": CLIENT_ID,
        "Api-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "filter": {"category_id": category_id},
        "limit": 10
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            print(f"status {resp.status_code}: {resp.text[:100]}")
            return None
        products = resp.json().get("result", {}).get("items", [])
        
        if not products:
            return None
        
        product_id = products[0].get("product_id")
        info_url = "https://api-seller.ozon.ru/v2/product/info"
        info_resp = requests.post(info_url, headers=headers, json={"product_id": product_id}, timeout=30)
        
        for comm in info_resp.json().get("result", {}).get("commissions", []):
            if comm.get("sale_schema") == "FBS":
                return comm.get("percent")
        
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    print("=== Test Ozon API ===\n")
    
    categories = get_categories()
    print(f"Categories received: {len(categories)}")
    
    test_categories = []
    for cat in categories[:50]:
        cat_id = cat.get("description_category_id")
        cat_name = cat.get("category_name")
        if cat_id and cat_name and "благотворительность" not in cat_name.lower():
            test_categories.append((cat_id, cat_name))
    
    print(f"\nTesting {len(test_categories)} categories...\n")
    
    commissions = {}
    for cat_id, cat_name in test_categories[:10]:
        print(f"  {cat_name}...", end=" ")
        percent = get_commission_via_product(cat_id)
        if percent:
            commissions[cat_name] = percent
            print(f"OK {percent}%")
        else:
            print("FAIL")
    
    print(f"\nTotal commissions: {len(commissions)}")
    print(json.dumps(commissions, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()