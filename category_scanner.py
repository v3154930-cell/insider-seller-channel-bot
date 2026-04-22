#!/usr/bin/env python3
"""
Сканер комиссий Ozon по ВСЕМ категориям
Использует неактивный магазин для создания тестовых товаров
"""
import os
import json
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional

# Данные неактивного магазина
CLIENT_ID = "4140504"
API_KEY = "5a14cdc1-2557-45ed-8e30-47a6823931d1"

HEADERS = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

class OzonCategoryScanner:
    def __init__(self):
        self.results = {}
        self.created_products = []
        self.data_dir = "/opt/newsbot/data"
        os.makedirs(self.data_dir, exist_ok=True)

    def get_all_categories(self) -> List[Dict]:
        """Получает дерево всех категорий"""
        url = "https://api-seller.ozon.ru/v1/description-category/tree"
        resp = requests.post(url, headers=HEADERS, json={}, timeout=30)
        data = resp.json()
        if "result" in data:
            return data["result"]
        else:
            print(f"    [!] API Error {data.get('code', 'N/A')}: {data.get('message', 'Unknown')}")
            return []

    def flatten_categories(self, categories: List[Dict]) -> List[Dict]:
        """Разворачивает дерево категорий в плоский список (parent_category + type)"""
        flat = []

        def traverse(cats):
            for cat in cats:
                cat_id = cat.get("description_category_id")
                cat_name = cat.get("category_name")
                children = cat.get("children", [])

                # Категория может быть промежуточной и иметь детей с type_id
                # Если у детей есть type_id — это валидные комбинации для импорта
                for child in children:
                    if child.get("type_id"):
                        flat.append({
                            "category_id": cat_id,         # parent category_id
                            "type_id": child.get("type_id"), # type_id from child
                            "name": f"{cat_name} — {child.get('type_name', '')}"
                        })

                # Рекурсивно обходим подкатегории
                if children:
                    traverse(children)

        traverse(categories)
        return flat

    def get_category_attributes(self, category_id: int, type_id: int) -> List:
        """Получает обязательные атрибуты для категории"""
        url = "https://api-seller.ozon.ru/v1/description-category/attribute"
        payload = {
            "description_category_id": category_id,
            "type_id": type_id
        }

        try:
            resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
            attributes = resp.json().get("result", [])
            return [attr for attr in attributes if attr.get("is_required")]
        except Exception as e:
            print(f"    [!] Attribute error: {e}")
            return []

    def get_default_value_for_attribute(self, attr: Dict) -> str:
        """Возвращает значение-заглушку для атрибута по его типу"""
        attr_type = attr.get("type", "string")

        if attr_type == "string":
            return "Тестовое значение"
        elif attr_type == "integer":
            return "1"
        elif attr_type == "boolean":
            return "true"
        elif attr_type == "float":
            return "1.0"
        elif attr_type == "date":
            return "2024-01-01"
        else:
            return "test"

    def create_product(self, category_id: int, type_id: int, category_name: str) -> Optional[int]:
        """Создает тестовый товар в категории"""
        url = "https://api-seller.ozon.ru/v3/product/import"

        required_attrs = self.get_category_attributes(category_id, type_id)
        print(f"    [DEBUG] category_id={category_id} type_id={type_id} required_attrs={len(required_attrs)}")

        attributes = []
        for attr in required_attrs:
            attr_id = attr.get("id")
            if attr_id:
                attributes.append({
                    "id": attr_id,
                    "values": [{"value": self.get_default_value_for_attribute(attr)}]
                })

        offer_id = f"__scanner_{category_id}_{type_id}"

        product = {
            "offer_id": offer_id,
            "name": f"Scanner {category_name[:50]}",
            "description": "Тестовый товар для получения комиссии. Будет удален.",
            "category_id": category_id,
            "type_id": type_id,
            "price": "1000",
            "vat": "0.1",
            "images": ["https://img.freepik.com/free-photo/white-product_53876-66988.jpg"],
            "attributes": attributes
        }

        print(f"    [DEBUG] offer_id={offer_id} attributes_count={len(attributes)}")

        try:
            resp = requests.post(url, headers=HEADERS, json={"items": [product]}, timeout=30)
            print(f"    [DEBUG] import response status={resp.status_code} text={resp.text[:200]}")
            data = resp.json()
            task_id = data.get("result", {}).get("task_id")

            if task_id:
                return task_id
            else:
                print(f"    [!] Error: {data.get('error', 'Unknown')}")
                return None
        except Exception as e:
            print(f"    [X] Create error: {e}")
            return None

    def wait_for_import(self, task_id: int, max_wait: int = 45) -> Optional[str]:
        """Ожидает завершения импорта, возвращает offer_id"""
        url = "https://api-seller.ozon.ru/v1/product/import/info"
        start = time.time()

        while time.time() - start < max_wait:
            try:
                resp = requests.post(url, headers=HEADERS, json={"task_id": task_id}, timeout=30)
                items = resp.json().get("result", {}).get("items", [])

                if items:
                    status = items[0].get("status")
                    if status == "imported":
                        return items[0].get("offer_id")
                    elif status == "failed":
                        errors = items[0].get("errors", [])
                        print(f"    [X] Import failed: {errors}")
                        return None
            except Exception as e:
                print(f"    [!] Wait error: {e}")

            time.sleep(2)

        return None

    def get_commission(self, offer_id: str) -> Optional[float]:
        """Получает комиссию по offer_id"""
        url = "https://api-seller.ozon.ru/v3/product/info/list"
        payload = {"offer_id": [offer_id]}

        try:
            resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
            items = resp.json().get("items", [])

            if items:
                commissions = items[0].get("commissions", [])
                for comm in commissions:
                    percent = comm.get("percent")
                    if percent:
                        return percent
            return None
        except Exception as e:
            print(f"    [!] Commission error: {e}")
            return None

    def scan_all(self, limit: int = None):
        """Сканирует все категории"""
        print("=" * 60)
        print(f"[SCAN] Ozon Commission Scanner - {datetime.now()}")
        print("=" * 60)

        print("\n[*] Getting category tree...")
        categories_tree = self.get_all_categories()
        print(f"[OK] Tree received")

        categories = self.flatten_categories(categories_tree)
        print(f"[*] Found {len(categories)} categories")
        if categories:
            print(f"[DEBUG] First: {categories[0]}")

        if limit:
            categories = categories[:limit]
            print(f"[TEST] Limited to {limit} categories")

        commissions = {}
        success_count = 0
        fail_count = 0

        for i, cat in enumerate(categories):
            cat_id = cat.get("category_id")
            cat_name = cat.get("name")
            type_id = cat.get("type_id")

            print(f"\n[{i+1}/{len(categories)}] {cat_name}")

            if not type_id:
                print(f"    [!] No type_id — skipping")
                fail_count += 1
                continue

            task_id = self.create_product(cat_id, type_id, cat_name)
            if not task_id:
                print(f"    [X] Failed to create product")
                fail_count += 1
                continue

            offer_id = self.wait_for_import(task_id)
            if not offer_id:
                print(f"    [X] Import did not complete")
                fail_count += 1
                continue

            percent = self.get_commission(offer_id)
            if percent:
                commissions[cat_name] = percent
                success_count += 1
                print(f"    [OK] Commission: {percent}%")
            else:
                print(f"    [!] Commission not received")
                fail_count += 1

            time.sleep(1)

        result = {
            "timestamp": datetime.now().isoformat(),
            "total_categories": len(categories),
            "success": success_count,
            "failed": fail_count,
            "commissions": commissions
        }

        output_file = os.path.join(self.data_dir, "ozon_commissions_all.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 60)
        print(f"RESULTS:")
        print(f"   [OK] Success: {success_count}")
        print(f"   [X] Failed: {fail_count}")
        print(f"   [*] Saved to: {output_file}")
        print("=" * 60)


if __name__ == "__main__":
    scanner = OzonCategoryScanner()
    # Тестовый запуск: первые 10 категорий
    scanner.scan_all(limit=10)
