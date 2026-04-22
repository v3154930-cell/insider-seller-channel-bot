#!/usr/bin/env python3
"""
Test Ozon API — getting commissions via offer (no products needed)
"""
import requests
import json

CLIENT_ID = "2548826"
API_KEY = "9f9b3abe-49ae-4f7d-99ad-5211434a8ff8"

def get_commission_via_offer():
    """Try to get commission via offer method"""
    url = "https://api-seller.ozon.ru/v1/commission/offer"
    headers = {
        "Client-Id": CLIENT_ID,
        "Api-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "offer_id": "test_offer_123",
        "price": "1000"
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"Status: {resp.status_code}, Response: {resp.text[:200]}")
        return resp.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    get_commission_via_offer()