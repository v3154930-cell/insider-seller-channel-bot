import subprocess
import sys

result = subprocess.run(
    [sys.executable, "category_scanner.py"],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace',
    cwd=r"D:\LLM code\insider-seller-channel-bot"
)

print(result.stdout)
print(result.stderr)
print("Return code:", result.returncode)
