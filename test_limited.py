#!/usr/bin/env python3
import sys
sys.path.append(r"D:\LLM code\insider-seller-channel-bot")

from category_scanner import OzonCategoryScanner

print("=" * 60)
print("TEST MODE: 5 categories")
print("=" * 60)
scanner = OzonCategoryScanner()
scanner.scan_all(limit=5)
