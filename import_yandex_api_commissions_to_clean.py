#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import time
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, date

BASE = Path("/opt/newsbot_v2")
DB_PATH = BASE / "data" / "unified_tariffs.db"
CACHE_DIR = BASE / "rules_docs" / "api_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://api.partner.market.yandex.ru"

MARKETPLACE = "yandex"
FEE_TYPE = "commission_only"
SOURCE_FILE = "yandex_market_api_tariffs_calculate.json"

PRICE = 1000
LENGTH = 10
WIDTH = 10
HEIGHT = 10
WEIGHT = 0.5
BATCH_SIZE = 200

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

def request_json(method, path, body=None, timeout=90):
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Yandex API HTTP {e.code}: {raw[:3000]}")

def norm_text(value):
    s = str(value or "").strip().lower().replace("ё", "е")
    s = re.sub(r"[^0-9a-zа-я]+", " ", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    return s

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
            "category_id": int(cid),
            "name": name,
            "path": " > ".join(new_path),
        })

    for child in children:
        walk_categories(child, new_path, out)

    return out

def get_active_campaigns():
    status, data = request_json("GET", "/v2/campaigns")
    if status != 200:
        raise RuntimeError(f"/v2/campaigns status={status}")

    campaigns = data.get("campaigns", [])
    active = [
        c for c in campaigns
        if str(c.get("apiAvailability")) == "AVAILABLE"
    ]

    if not active:
        raise RuntimeError("No active Yandex campaigns")

    return active

def get_leaf_categories():
    status, data = request_json("POST", "/v2/categories/tree", {})
    if status != 200:
        raise RuntimeError(f"/v2/categories/tree status={status}")

    root = data.get("result")
    leaves = walk_categories(root)

    if len(leaves) < 1000:
        raise RuntimeError(f"Too few Yandex leaf categories: {len(leaves)}")

    return leaves

def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]

def tariff_params(tariff):
    d = {}
    for p in tariff.get("parameters", []) or []:
        if p.get("name"):
            d[str(p.get("name"))] = p.get("value")
    return d

def extract_fee_percent(tariffs):
    for t in tariffs or []:
        if str(t.get("type")) != "FEE":
            continue

        params = tariff_params(t)
        if str(params.get("valueType") or "").lower() != "relative":
            continue

        value = params.get("value")
        if value is None:
            continue

        return float(str(value).replace(",", "."))

    return None

def calc_campaign(campaign, leaves):
    campaign_id = int(campaign["id"])
    scheme = str(campaign.get("placementType") or "UNKNOWN").upper()

    print(f"=== CAMPAIGN {campaign_id} {scheme} ===")

    by_id = {x["category_id"]: x for x in leaves}
    result_rows = []
    raw_samples = []

    batch_no = 0

    for batch in chunks(leaves, BATCH_SIZE):
        batch_no += 1

        body = {
            "parameters": {
                "campaignId": campaign_id
            },
            "offers": [
                {
                    "categoryId": x["category_id"],
                    "price": PRICE,
                    "length": LENGTH,
                    "width": WIDTH,
                    "height": HEIGHT,
                    "weight": WEIGHT,
                    "quantity": 1,
                }
                for x in batch
            ]
        }

        status, data = request_json("POST", "/v2/tariffs/calculate", body)

        if status != 200 or data.get("status") != "OK":
            raise RuntimeError(
                f"tariffs/calculate failed campaign={campaign_id} batch={batch_no}: {str(data)[:1000]}"
            )

        offers = ((data.get("result") or {}).get("offers") or [])
        if len(raw_samples) < 10:
            raw_samples.extend(offers[:2])

        for item in offers:
            offer = item.get("offer") or {}
            category_id = int(offer.get("categoryId"))
            category = by_id.get(category_id)

            if not category:
                continue

            fee = extract_fee_percent(item.get("tariffs") or [])
            if fee is None:
                continue

            result_rows.append({
                "campaign_id": campaign_id,
                "scheme": scheme,
                "category_id": category_id,
                "category": category["path"],
                "product_type": category["name"],
                "fee_percent": fee,
            })

        print(f"batch={batch_no} rows={len(result_rows)}")
        time.sleep(0.15)

    cache_path = CACHE_DIR / f"yandex_tariffs_calculate_{campaign_id}_{scheme}.json"
    cache_path.write_text(json.dumps({
        "campaign": campaign,
        "sample_rows": raw_samples,
        "rows_count": len(result_rows),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    return result_rows

def table_columns(cur, table):
    return [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]

def insert_clean(rows):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    valid_from = date.today().strftime("%Y-%m-%d")

    clean = []

    for r in rows:
        clean.append({
            "marketplace": MARKETPLACE,
            "category": r["category"],
            "product_type": r["product_type"],
            "scheme": r["scheme"],
            "fee_percent": float(r["fee_percent"]),
            "fee_type": FEE_TYPE,
            "valid_from": valid_from,
            "source_file": SOURCE_FILE,
            "source_note": f"category_id={r['category_id']}; campaign_id={r['campaign_id']}; api=tariffs/calculate; price={PRICE}",
            "created_at": now,
            "product_type_norm": norm_text(r["product_type"]),
            "category_norm": norm_text(r["category"]),
        })

    if len(clean) < 5000:
        raise RuntimeError(f"Too few Yandex rows prepared: {len(clean)}")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cols = table_columns(cur, "clean_commissions")
    insert_cols = [c for c in cols if c != "id" and c in clean[0]]

    old_count = cur.execute(
        "SELECT COUNT(*) FROM clean_commissions WHERE marketplace=? AND fee_type=?",
        (MARKETPLACE, FEE_TYPE),
    ).fetchone()[0]

    print(f"Old Yandex rows: {old_count}")
    print(f"New Yandex rows: {len(clean)}")

    if old_count and len(clean) < int(old_count * 0.7):
        raise RuntimeError(f"Suspicious row drop: old={old_count}, new={len(clean)}")

    placeholders = ",".join(["?"] * len(insert_cols))
    col_sql = ",".join(insert_cols)

    values = [tuple(row.get(c) for c in insert_cols) for row in clean]

    try:
        cur.execute("BEGIN")
        cur.execute(
            "DELETE FROM clean_commissions WHERE marketplace=? AND fee_type=?",
            (MARKETPLACE, FEE_TYPE),
        )
        cur.executemany(
            f"INSERT INTO clean_commissions ({col_sql}) VALUES ({placeholders})",
            values,
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    print(f"OK: replaced Yandex clean_commissions rows: {len(clean)}")

def main():
    load_env()

    if not DB_PATH.exists():
        raise RuntimeError(f"DB not found: {DB_PATH}")

    campaigns = get_active_campaigns()
    leaves = get_leaf_categories()

    print(f"Active campaigns: {len(campaigns)}")
    print(f"Leaf categories: {len(leaves)}")

    all_rows = []

    for campaign in campaigns:
        rows = calc_campaign(campaign, leaves)
        all_rows.extend(rows)

    seen = set()
    dedup = []

    for r in all_rows:
        key = (r["campaign_id"], r["scheme"], r["category_id"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)

    print(f"Total rows before dedup: {len(all_rows)}")
    print(f"Total rows after dedup: {len(dedup)}")

    summary_path = CACHE_DIR / "yandex_api_commissions_rows.json"
    summary_path.write_text(json.dumps(dedup, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved summary: {summary_path}")

    insert_clean(dedup)

if __name__ == "__main__":
    main()
