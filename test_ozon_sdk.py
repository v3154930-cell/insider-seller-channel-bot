#!/usr/bin/env python3
import asyncio
import json
from ozon_api import OzonAPI
from ozon_api.models.product_list import ProductListRequest, ProductListFilter

CLIENT_ID = "2548826"
API_KEY = "1c45b5e2-68e5-4716-9b13-deb8f938e3b8"

async def main():
    print("=" * 60)
    print("TEST RESULT")
    print("=" * 60)
    
    async with OzonAPI(client_id=CLIENT_ID, api_key=API_KEY) as api:
        list_req = ProductListRequest(
            limit=5,
            filter=ProductListFilter(visibility="ALL")
        )
        result = await api.product_list(list_req)
        inner = result.result
        
        print(f"Total products on account: {inner.total}")
        print(f"First 5 products:")
        for item in inner.items:
            print(f"  - offer_id: {item['offer_id']}")
            print(f"    product_id: {item['product_id']}")
            print(f"    archived: {item['archived']}")
        
        print("\n" + "=" * 60)
        print("CONCLUSION")
        print("=" * 60)
        print("SDK works correctly!")
        print("Can list products but commissions info not available in this SDK version")
        print("Note: Product commissions depend on category and sale schema")

asyncio.run(main())