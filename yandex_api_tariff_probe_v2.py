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
        try:
            data = json.loads(raw)
        except Exception:
            data = {"raw": raw}
        return e.code, data

def walk_categories(node, path=None, out=None):
    if out is None:
        out = []
    if path is None:
        path = []

    if not isinstance(node, dict):
        return out

    cid = node.get("id")
    name = str(node.get("name") or "").strip()
    children = node.get("children") or []

    new_path = path + [name] if name else path

    if cid and not children:
        out.append({
            "categoryId": int(cid),
            "name": name,
            "path": " > ".join(new_path),
        })

    for child in children:
        walk_categories(child, new_path, out)

    return out

def select_samples(leaves):
    wanted = [
        "шампун",
        "ботин",
        "крем",
        "космет",
        "чайник",
        "картина",
        "шапк",
    ]

    selected = []
    used = set()

    for word in wanted:
        for item in leaves:
            hay = (item["path"] + " " + item["name"]).lower()
            if word in hay and item["categoryId"] not in used:
                selected.append(item)
                used.add(item["categoryId"])
                break

    if not selected:
        selected = leaves[:5]

    return selected[:5]

def get_active_campaigns():
    status, data = request_json("GET", "/v2/campaigns")
    campaigns = data.get("campaigns", []) if isinstance(data, dict) else []

    active = [
        c for c in campaigns
        if str(c.get("apiAvailability")) == "AVAILABLE"
    ]

    print("=== CAMPAIGNS ===")
    print("STATUS:", status)
    for c in campaigns:
        print({
            "id": c.get("id"),
            "placementType": c.get("placementType"),
            "apiAvailability": c.get("apiAvailability"),
            "domain": c.get("domain"),
        })

    return active

def make_offers(sample):
    return [
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

def make_offers_weight_dimensions(sample):
    return [
        {
            "categoryId": x["categoryId"],
            "price": 1000,
            "weightDimensions": {
                "length": 10,
                "width": 10,
                "height": 10,
                "weight": 0.5,
            },
            "quantity": 1,
        }
        for x in sample
    ]

def try_tariffs(campaign_id, sample):
    base_offers = make_offers(sample)
    wd_offers = make_offers_weight_dimensions(sample)

    variants = [
        {
            "name": "A: parameters campaignId + flat dimensions",
            "body": {
                "parameters": {
                    "campaignId": campaign_id,
                    "currency": "RUR",
                    "frequency": "DAILY",
                },
                "offers": base_offers,
            },
        },
        {
            "name": "B: parameters campaignId only + flat dimensions",
            "body": {
                "parameters": {
                    "campaignId": campaign_id,
                },
                "offers": base_offers,
            },
        },
        {
            "name": "C: parameters campaignId + weightDimensions",
            "body": {
                "parameters": {
                    "campaignId": campaign_id,
                    "currency": "RUR",
                    "frequency": "DAILY",
                },
                "offers": wd_offers,
            },
        },
        {
            "name": "D: parameters campaignId only + weightDimensions",
            "body": {
                "parameters": {
                    "campaignId": campaign_id,
                },
                "offers": wd_offers,
            },
        },
    ]

    print()
    print("=== TARIFFS CALCULATE PROBE ===")
    print("campaign_id:", campaign_id)

    for v in variants:
        print()
        print("-----", v["name"], "-----")
        print("REQUEST_PREVIEW:")
        print(json.dumps(v["body"], ensure_ascii=False, indent=2)[:3000])

        status, data = request_json("POST", "/v2/tariffs/calculate", v["body"])
        print("STATUS:", status)
        print("RESPONSE_PREVIEW:")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:10000])

        if status == 200:
            print("OK_VARIANT:", v["name"])
            return v["name"], data

    return None, None

def main():
    load_env()

    active = get_active_campaigns()
    if not active:
        raise RuntimeError("No active Yandex campaigns with apiAvailability=AVAILABLE")

    env_campaign = os.getenv("YANDEX_MARKET_CAMPAIGN_ID")
    campaign_id = None

    if env_campaign:
        for c in active:
            if str(c.get("id")) == str(env_campaign):
                campaign_id = int(c["id"])
                break

    if campaign_id is None:
        campaign_id = int(active[0]["id"])

    print()
    print("SELECTED_CAMPAIGN_ID:", campaign_id)

    print()
    print("=== CATEGORIES TREE ===")
    status, tree = request_json("POST", "/v2/categories/tree", {})
    print("STATUS:", status)

    root = tree.get("result") if isinstance(tree, dict) else None
    if not root:
        print("NO RESULT:")
        print(json.dumps(tree, ensure_ascii=False, indent=2)[:6000])
        return

    leaves = walk_categories(root)
    print("LEAF_CATEGORIES:", len(leaves))

    print()
    print("=== SAMPLE LEAVES ===")
    for x in leaves[:20]:
        print(x)

    sample = select_samples(leaves)

    print()
    print("=== SELECTED SAMPLE ===")
    for x in sample:
        print(x)

    if not sample:
        raise RuntimeError("No sample categories selected")

    try_tariffs(campaign_id, sample)

if __name__ == "__main__":
    main()
