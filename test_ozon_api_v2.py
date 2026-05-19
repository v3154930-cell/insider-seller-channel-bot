import os
import json
import urllib.request
import urllib.error

CLIENT_ID = os.getenv("OZON_CLIENT_ID")
API_KEY = os.getenv("OZON_API_KEY")

if not CLIENT_ID:
    print("OZON_CLIENT_ID is missing")
    raise SystemExit(1)

if not API_KEY:
    print("OZON_API_KEY is missing")
    raise SystemExit(1)

url = "https://api-seller.ozon.ru/v1/description-category/tree"

body = json.dumps({
    "language": "DEFAULT"
}).encode("utf-8")

req = urllib.request.Request(
    url,
    data=body,
    headers={
        "Client-Id": CLIENT_ID,
        "Api-Key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "newsbot-v2/1.0",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        status = resp.status
        raw = resp.read().decode("utf-8", errors="ignore")

    print("STATUS:", status)
    print("RAW_LENGTH:", len(raw))
    print("RAW_PREVIEW:")
    print(raw[:2000])

    data = json.loads(raw)
    print("JSON_TYPE:", type(data).__name__)
    if isinstance(data, dict):
        print("JSON_KEYS:", list(data.keys())[:30])

except urllib.error.HTTPError as e:
    print("HTTP_ERROR:", e.code)
    print(e.read().decode("utf-8", errors="ignore")[:3000])
except Exception as e:
    print("ERROR:", repr(e))
