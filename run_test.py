#!/usr/bin/env python3
import sys
sys.path.append(r"D:\LLM code\insider-seller-channel-bot")

from category_scanner import OzonCategoryScanner

print("Starting scanner test...")
scanner = OzonCategoryScanner()
scanner.scan_all(limit=5)
