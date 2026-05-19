import os
import json
import urllib.request
import urllib.error

WB_API_KEY = os.getenv("WB_API_KEY")

if not WB_API_KEY:
    print("WB_API_KEY is missing")
    raise SystemExit(1)

url = "https://common-api.wildberries.ru/api/v1/tariffs/commission"

req = urllib.request.Request(
    url,
    headers={
        "Authorization": WB_API_KEY,
        "Content-Type": "application/json",
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
    print(raw[:1500])

    try:
        data = json.loads(raw)
        print("JSON_TYPE:", type(data).__name__)
        if isinstance(data, dict):
            print("JSON_KEYS:", list(data.keys())[:30])
        elif isinstance(data, list):
            print("LIST_LEN:", len(data))
            print("FIRST_ITEM:", data[0] if data else None)
    except Exception as e:
        print("JSON_PARSE_ERROR:", repr(e))

except urllib.error.HTTPError as e:
    print("HTTP_ERROR:", e.code)
    print(e.read().decode("utf-8", errors="ignore")[:2000])
except Exception as e:
    print("ERROR:", repr(e))
