import os
import json
import urllib.request
import urllib.error

TOKEN = os.getenv("YANDEX_MARKET_TOKEN")

if not TOKEN:
    print("YANDEX_MARKET_TOKEN is missing")
    raise SystemExit(1)

url = "https://api.partner.market.yandex.ru/v2/campaigns"

req = urllib.request.Request(
    url,
    headers={
        "Api-Key": TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "newsbot-v2/1.0",
    },
    method="GET",
)

try:
    with urllib.request.urlopen(req, timeout=40) as resp:
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
