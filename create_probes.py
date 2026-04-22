#!/usr/bin/env python3
"""
Creates probe products in all Ozon categories (one-time setup)
With zero stock - safe, not for sale
"""
import requests
import time

CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"

HEADERS = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

def get_all_categories():
    """Get all leaf categories"""
    url = "https://api-seller.ozon.ru/v1/description-category/tree"
    resp = requests.post(url, headers=HEADERS, json={})
    categories = resp.json().get("result", [])
    
    result = []
    def traverse(cats):
        for cat in cats:
            cat_id = cat.get("description_category_id")
            cat_name = cat.get("category_name")
            children = cat.get("children", [])
            
            has_leaf = False
            for child in children:
                if child.get("type_id"):
                    has_leaf = True
                    result.append({
                        "id": child.get("description_category_id") or cat_id,
                        "name": child.get("category_name") or cat_name,
                        "type_id": child.get("type_id")
                    })
            
            if not has_leaf and children:
                traverse(children)
            elif not has_leaf and not children:
                result.append({
                    "id": cat_id,
                    "name": cat_name,
                    "type_id": None
                })
    
    traverse(categories)
    return result

def create_product(cat_id, type_id, cat_name):
    """Create probe product in category"""
    url = "https://api-seller.ozon.ru/v3/product/import"
    
    product = {
        "offer_id": f"insider_probe_{cat_id}",
        "name": f"[INSIDER] {cat_name[:60]}",
        "description": "Service product for commission monitoring. Not for sale.",
        "category_id": cat_id,
        "price": "1000",
        "vat": "0.1"
    }
    
    if type_id:
        product["type_id"] = type_id
    
    try:
        resp = requests.post(url, headers=HEADERS, json={"items": [product]}, timeout=30)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def wait_for_import(task_id):
    """Wait for import to complete, return product_id"""
    url = "https://api-seller.ozon.ru/v1/product/import/info"
    for _ in range(10):
        time.sleep(2)
        resp = requests.post(url, headers=HEADERS, json={"task_id": task_id})
        items = resp.json().get("result", {}).get("items", [])
        if items:
            status = items[0].get("status")
            if status == "imported":
                return items[0].get("product_id")
            elif status == "failed":
                return None
    return None

def set_zero_stock(product_id):
    """Set zero stock - product not for sale"""
    url_wh = "https://api-seller.ozon.ru/v2/warehouse/list"
    resp = requests.post(url_wh, headers=HEADERS, json={"limit": 100})
    warehouses = resp.json().get("result", [])
    
    if not warehouses:
        warehouse_id = 0
    else:
        warehouse_id = warehouses[0].get("warehouse_id")
    
    url = "https://api-seller.ozon.ru/v2/products/stocks"
    payload = {
        "stocks": [{
            "product_id": product_id,
            "stock": 0,
            "warehouse_id": warehouse_id
        }]
    }
    requests.post(url, headers=HEADERS, json=payload)

def main():
    print("=" * 60)
    print("Creating probe products (zero stock) - Ozon")
    print("=" * 60)
    
    categories = get_all_categories()
    print(f"\nFound categories: {len(categories)}")
    
    created = 0
    failed = 0
    
    for i, cat in enumerate(categories):
        cat_id = cat["id"]
        cat_name = cat["name"]
        type_id = cat.get("type_id")
        
        print(f"[{i+1}/{len(categories)}] {cat_name[:50]}...", end=" ", flush=True)
        
        result = create_product(cat_id, type_id, cat_name)
        
        if "error" in result:
            print(f"FAIL: {result['error']}")
            failed += 1
            continue
        
        task_id = result.get("result", {}).get("task_id")
        if not task_id:
            print("FAIL: no task_id")
            failed += 1
            continue
        
        product_id = wait_for_import(task_id)
        if not product_id:
            print("FAIL: import incomplete")
            failed += 1
            continue
        
        set_zero_stock(product_id)
        
        print(f"OK (ID: {product_id})")
        created += 1
        
        time.sleep(0.3)
    
    print("\n" + "=" * 60)
    print(f"RESULTS:")
    print(f"   Created: {created}")
    print(f"   Failed: {failed}")
    print("=" * 60)

if __name__ == "__main__":
    main()