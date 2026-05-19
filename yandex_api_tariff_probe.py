#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = "https://api.partner.market.yandex.ru"

def load_env(path="/opt/newsbot_v2/.env"):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def request_json(method, path, body=None):
    token = os.getenv("YANDEX_MARKET_TOKEN")
    if not token:
        raise RuntimeError("YANDEX_MARKET_TOKEN is missing")

    raw_body = None
    if body is not None:
        raw_body = json.dumps(body, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        BASE_URL + path,
        data=raw_body,
        headers={
            "Api-Key": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "newsbot-v2/1.0",
        },
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        print("HTTP_ERROR:", e.code)
        print(raw[:6000])
        raise

def walk_categories(obj, path=None, out=None):
    if out is None:
        out = []
    if path is None:
        path = []

    if isinstance(obj, dict):
        cid = obj.get("id") or obj.get("categoryId")
        name = obj.get("name") or obj.get("categoryName") or ""
        children = obj.get("children") or obj.get("categories") or []

        new_path = path + [str(name)] if name else path

        if cid and not children:
            out.append({
                "categoryId": int(cid),
                "name": str(name),
                "path": " > ".join(new_path),
            })

        for child in children:
            walk_categories(child, new_path, out)

    elif isinstance(obj, list):
        for item in obj:
            walk_categories(item, path, out)

    return out

def find_sample_categories(leaves):
    wanted = [
        "шампун",
        "ботин",
        "космет",
        "крем",
        "чайник",
        "картина",
        "шапк",
    ]

    selected = []
    seen = set()

    for w in wanted:
        for x in leaves:
            hay = (x["path"] + " " + x["name"]).lower()
            if w in hay and x["categoryId"] not in seen:
                selected.append(x)
                seen.add(x["categoryId"])
                break

    if not selected:
        selected = leaves[:5]

    return selected[:10]

def main():
    load_env()

    print("=== CATEGORIES TREE ===")
    status, tree = request_json("POST", "/v2/categories/tree", {})
    print("STATUS:", status)
    print("TOP_KEYS:", list(tree.keys()) if isinstance(tree, dict) else type(tree).__name__)

    leaves = walk_categories(tree)
    print("LEAF_CATEGORIES:", len(leaves))

    print()
    print("=== SAMPLE LEAVES ===")
    for x in leaves[:20]:
        print(x)

    sample = find_sample_categories(leaves)

    print()
    print("=== SELECTED FOR TARIFF TEST ===")
    for x in sample:
        print(x)

    body = {
        "offers": [
            {
                "categoryId": x["categoryId"],
                "price": 1000,
                "length": 10,
                "width": 10,
                "height": 10,
                "weight": 0.5,
                "quantity": 1,
            }
            for x in sample
        ]
    }

    print()
    print("=== TARIFFS CALCULATE ===")
    print("REQUEST:")
    print(json.dumps(body, ensure_ascii=False, indent=2))

    status, tariffs = request_json("POST", "/v2/tariffs/calculate", body)
    print("STATUS:", status)
    print("RESPONSE_PREVIEW:")
    print(json.dumps(tariffs, ensure_ascii=False, indent=2)[:12000])

if __name__ == "__main__":
    main()
