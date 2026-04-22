#!/usr/bin/env python3
import sys
import os
sys.path.append(r"D:\LLM code\insider-seller-channel-bot")

from category_scanner import OzonCategoryScanner

# Redirect stdout to file
original_stdout = sys.stdout
log_file = open(r"D:\LLM code\insider-seller-channel-bot\test_output.log", "w", encoding="utf-8")
sys.stdout = log_file

try:
    scanner = OzonCategoryScanner()
    scanner.scan_all(limit=5)
finally:
    sys.stdout = original_stdout
    log_file.close()

print("Test completed. Output saved to test_output.log")
