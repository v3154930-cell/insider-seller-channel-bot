#!/usr/bin/env python3
from ozon_api.models.product_info_list import ProductInfoListRequest
import inspect

print("ProductInfoListRequest fields:")
for name, field in ProductInfoListRequest.model_fields.items():
    print(f"  {name}: {field.annotation}")