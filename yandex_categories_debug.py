#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import urllib.request
from pathlib import Path

def load_env(path="/opt/newsbot_v2/.env"):
    p = Path(path)
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def req(path, body):
    token = os.environ["YANDEX_MARKET_TOKEN"]
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(
        "https://api.partner.market.yandex.ru" + path,
        data=data,
        headers={
            "Api-Key": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "newsbot-v2/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(r, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw)

def main():
    load_env()
    data = req("/v2/categories/tree", {})
    print("TOP:", list(data.keys()))
    result = data.get("result")
    print("RESULT_TYPE:", type(result).__name__)

    if isinstance(result, dict):
        print("RESULT_KEYS:", list(result.keys()))
        for k, v in result.items():
            print("KEY:", k, "TYPE:", type(v).__name__)
            print(json.dumps(v, ensure_ascii=False, indent=2)[:3000])
            print("-" * 80)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2)[:6000])

if __name__ == "__main__":
    main()
