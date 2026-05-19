#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import sqlite3
from pathlib import Path
from collections import defaultdict, Counter

DB = Path("/opt/newsbot_v2/data/unified_tariffs.db")
OUT = Path(__file__).resolve().parent
EXPECTED_SCHEMES = {"FBY", "FBS", "EXPRESS", "DBS"}

def s(v):
    return "" if v is None else str(v).strip()

def write_csv(name, rows, fields):
    path = OUT / name
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    return path

def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    source_summary = [dict(r) for r in cur.execute("""
        SELECT
            fee_type,
            source_file,
            source_note,
            COUNT(*) AS rows_count,
            COUNT(DISTINCT category) AS categories_count,
            COUNT(DISTINCT product_type) AS product_types_count,
            MIN(valid_from) AS min_valid_from,
            MAX(valid_from) AS max_valid_from,
            MIN(fee_percent) AS min_fee,
            MAX(fee_percent) AS max_fee
        FROM clean_commissions
        WHERE marketplace = 'ozon'
        GROUP BY fee_type, source_file, source_note
        ORDER BY rows_count DESC
    """)]

    rows = [dict(r) for r in cur.execute("""
        SELECT
            id, marketplace, category, product_type, scheme, fee_percent,
            fee_type, valid_from, source_file, source_note, created_at
        FROM clean_commissions
        WHERE marketplace = 'ozon'
          AND fee_type = 'marketplace_service_rate'
        ORDER BY category, product_type, scheme
    """)]

    grouped = defaultdict(list)
    for r in rows:
        key = (s(r["category"]), s(r["product_type"]), s(r["source_file"]), s(r["valid_from"]))
        grouped[key].append(r)

    all_groups = []
    low_fee = []
    high_fee = []
    big_spread = []
    missing_schemes = []
    suspicious_select = []
    unusual_scheme_rows = []
    empty_rows = []

    fee_counter = Counter()
    source_counter = Counter()

    for r in rows:
        fee = float(r["fee_percent"] or 0)
        fee_counter[fee] += 1
        source_counter[s(r["source_file"])] += 1

        text_source = (s(r["source_file"]) + " " + s(r["source_note"])).lower()
        if "select" in text_source or "селект" in text_source:
            suspicious_select.append(r)

        if not s(r["category"]) or not s(r["product_type"]):
            empty_rows.append(r)

        if s(r["scheme"]) not in EXPECTED_SCHEMES:
            unusual_scheme_rows.append(r)

    for (category, product_type, source_file, valid_from), items in grouped.items():
        schemes = {}
        for item in items:
            schemes[s(item["scheme"])] = float(item["fee_percent"] or 0)

        fees = list(schemes.values())
        min_fee = min(fees) if fees else 0
        max_fee = max(fees) if fees else 0
        spread = max_fee - min_fee
        scheme_set = set(schemes.keys())

        missing = sorted(EXPECTED_SCHEMES - scheme_set)
        unusual = sorted(scheme_set - EXPECTED_SCHEMES)

        flags = []
        if min_fee <= 5:
            flags.append("LOW_FEE_5_OR_LESS")
        if max_fee >= 40:
            flags.append("HIGH_FEE_40_OR_MORE")
        if spread >= 20:
            flags.append("LARGE_SPREAD_20_OR_MORE")
        if missing:
            flags.append("MISSING_SCHEMES")
        if unusual:
            flags.append("UNUSUAL_SCHEMES")

        row = {
            "category": category,
            "product_type": product_type,
            "schemes": ", ".join(f"{k}={v:g}%" for k, v in sorted(schemes.items())),
            "scheme_count": len(scheme_set),
            "missing_schemes": ", ".join(missing),
            "unusual_schemes": ", ".join(unusual),
            "min_fee": min_fee,
            "max_fee": max_fee,
            "spread": spread,
            "source_file": source_file,
            "valid_from": valid_from,
            "flags": ", ".join(flags),
        }

        all_groups.append(row)

        if min_fee <= 5:
            low_fee.append(row)
        if max_fee >= 40:
            high_fee.append(row)
        if spread >= 20:
            big_spread.append(row)
        if missing:
            missing_schemes.append(row)

    all_groups.sort(key=lambda x: (x["category"], x["product_type"], float(x["min_fee"])))
    low_fee.sort(key=lambda x: (float(x["min_fee"]), x["product_type"]))
    high_fee.sort(key=lambda x: (-float(x["max_fee"]), x["product_type"]))
    big_spread.sort(key=lambda x: (-float(x["spread"]), x["product_type"]))
    missing_schemes.sort(key=lambda x: (x["category"], x["product_type"]))

    group_fields = [
        "category", "product_type", "schemes", "scheme_count",
        "missing_schemes", "unusual_schemes",
        "min_fee", "max_fee", "spread",
        "source_file", "valid_from", "flags"
    ]

    row_fields = [
        "id", "marketplace", "category", "product_type", "scheme",
        "fee_percent", "fee_type", "valid_from", "source_file",
        "source_note", "created_at"
    ]

    source_fields = [
        "fee_type", "source_file", "source_note", "rows_count",
        "categories_count", "product_types_count",
        "min_valid_from", "max_valid_from", "min_fee", "max_fee"
    ]

    files = []
    files.append(write_csv("01_ozon_sources_summary.csv", source_summary, source_fields))
    files.append(write_csv("02_ozon_all_grouped_categories.csv", all_groups, group_fields))
    files.append(write_csv("03_ozon_low_fee_5_or_less.csv", low_fee, group_fields))
    files.append(write_csv("04_ozon_high_fee_40_or_more.csv", high_fee, group_fields))
    files.append(write_csv("05_ozon_large_spread_20_or_more.csv", big_spread, group_fields))
    files.append(write_csv("06_ozon_missing_schemes.csv", missing_schemes, group_fields))
    files.append(write_csv("07_ozon_suspicious_select_rows.csv", suspicious_select, row_fields))
    files.append(write_csv("08_ozon_empty_category_or_product_type.csv", empty_rows, row_fields))
    files.append(write_csv("09_ozon_unusual_scheme_rows.csv", unusual_scheme_rows, row_fields))

    summary_path = OUT / "00_SUMMARY.txt"
    with summary_path.open("w", encoding="utf-8") as f:
        f.write("OZON FULL TARIFF AUDIT / QUIET\n")
        f.write(f"DB: {DB}\n")
        f.write(f"OUT: {OUT}\n\n")

        f.write("SOURCE SUMMARY:\n")
        for r in source_summary:
            f.write(str(r) + "\n")

        f.write("\nCOUNTS:\n")
        f.write(f"marketplace_service_rate rows: {len(rows)}\n")
        f.write(f"grouped categories/product_types: {len(all_groups)}\n")
        f.write(f"low fee <= 5 groups: {len(low_fee)}\n")
        f.write(f"high fee >= 40 groups: {len(high_fee)}\n")
        f.write(f"large spread >= 20 groups: {len(big_spread)}\n")
        f.write(f"missing schemes groups: {len(missing_schemes)}\n")
        f.write(f"suspicious Select rows: {len(suspicious_select)}\n")
        f.write(f"empty category/product_type rows: {len(empty_rows)}\n")
        f.write(f"unusual scheme rows: {len(unusual_scheme_rows)}\n\n")

        f.write("TOP 30 LOW FEE:\n")
        for r in low_fee[:30]:
            f.write(f"{r['min_fee']}–{r['max_fee']} | {r['product_type']} | {r['category']} | {r['schemes']}\n")

        f.write("\nTOP 30 HIGH FEE:\n")
        for r in high_fee[:30]:
            f.write(f"{r['min_fee']}–{r['max_fee']} | {r['product_type']} | {r['category']} | {r['schemes']}\n")

        f.write("\nTOP 30 BIG SPREAD:\n")
        for r in big_spread[:30]:
            f.write(f"spread={r['spread']} | {r['min_fee']}–{r['max_fee']} | {r['product_type']} | {r['category']} | {r['schemes']}\n")

        f.write("\nSOURCE FILES:\n")
        for src, cnt in source_counter.most_common():
            f.write(f"{cnt}: {src}\n")

        f.write("\nFEE DISTRIBUTION:\n")
        for fee, cnt in sorted(fee_counter.items()):
            f.write(f"{fee:g}%: {cnt}\n")

    print("=== SUMMARY ===")
    print("OUT:", OUT)
    print("marketplace_service_rate rows:", len(rows))
    print("grouped categories/product_types:", len(all_groups))
    print("low fee <= 5 groups:", len(low_fee))
    print("high fee >= 40 groups:", len(high_fee))
    print("large spread >= 20 groups:", len(big_spread))
    print("missing schemes groups:", len(missing_schemes))
    print("suspicious Select rows:", len(suspicious_select))
    print("empty category/product_type rows:", len(empty_rows))
    print("unusual scheme rows:", len(unusual_scheme_rows))
    print()
    print("SUMMARY FILE:", summary_path)
    print()
    print("CSV FILES:")
    for fpath in files:
        print(fpath)

    conn.close()

if __name__ == "__main__":
    main()
