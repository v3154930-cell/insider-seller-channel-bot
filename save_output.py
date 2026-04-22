import subprocess
import sys

with open(r"D:\LLM code\insider-seller-channel-bot\scan_results.txt", "w", encoding="utf-8") as f:
    result = subprocess.run(
        [sys.executable, "-c", "from category_scanner import OzonCategoryScanner; scanner = OzonCategoryScanner(); scanner.scan_all(limit=5)"],
        capture_output=True,
        text=True,
        cwd=r"D:\LLM code\insider-seller-channel-bot",
        encoding='utf-8',
        errors='replace'
    )
    f.write(result.stdout)
    f.write(result.stderr)
    f.write(f"\nReturn code: {result.returncode}")

print("Output saved to scan_results.txt")
