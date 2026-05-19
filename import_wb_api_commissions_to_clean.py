#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

BASE = Path("/opt/newsbot_v2")
DB_PATH = BASE / "data" / "unified_tariffs.db"
CACHE_PATH = BASE / "rules_docs" / "api_cache" / "wb_commissions.json"

SOURCE_FILE = "wb_api_commissions.json"
MARKETPLACE = "wb"
FEE_TYPE = "commission_only"

FEE_FIELDS = [
    "kgvpMarketplace",
    "kgvpSupplier",
    "kgvpSupplierExpress",
    "kgvpPickup",
    "kgvpBooking",
    "paidStorageKgvp",
]

SCHEME_LABELS = {
    "kgvpMarketplace": "kgvpMarketplace",
    "kgvpSupplier": "kgvpSupplier",
    "kgvpSupplierExpress": "kgvpSupplierExpress",
    "kgvpPickup": "kgvpPickup",
    "kgvpBooking": "kgvpBooking",
    "paidStorageKgvp": "paidStorageKgvp",
}

def norm_text(value: Any) -> str:
    s = str(value or "").strip().lower()
    s = s.replace("ё", "е")
    s = re.sub(r"[^0-9a-zа-я]+", " ", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def as_float(value: Any):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("%", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None

def get_any(d: Dict[str, Any], keys: List[str]):
    lower_map = {str(k).lower(): k for k in d.keys()}
    for k in keys:
        real = lower_map.get(k.lower())
        if real is not None:
            return d.get(real)
    return None

def walk(obj: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(obj, dict):
        # WB row usually has subject/category fields and kgvp* fee fields.
        has_fee = any(k in obj for k in FEE_FIELDS)
        has_subject = any(
            str(k).lower() in {
                "subjectid", "subject_id", "subjectname", "subject_name",
                "name", "parentid", "parent_id", "parentname", "parent_name"
            }
            for k in obj.keys()
        )
        if has_fee and has_subject:
            yield obj

        for v in obj.values():
            yield from walk(v)

    elif isinstance(obj, list):
        for x in obj:
            yield from walk(x)

def load_api_rows() -> List[Dict[str, Any]]:
    if not CACHE_PATH.exists():
        raise RuntimeError(f"Cache not found: {CACHE_PATH}")

    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    rows = list(walk(data))

    # Deduplicate by subject/category identity.
    seen = set()
    result = []
    for r in rows:
        subject_id = get_any(r, ["subjectID", "subject_id", "subjectId", "id"])
        subject_name = get_any(r, ["subjectName", "subject_name", "name"])
        parent_id = get_any(r, ["parentID", "parent_id", "parentId"])
        parent_name = get_any(r, ["parentName", "parent_name", "parent"])
        key = (str(parent_id), str(parent_name), str(subject_id), str(subject_name))
        if key in seen:
            continue
        seen.add(key)
        result.append(r)

    return result

def build_clean_rows(api_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    valid_from = date.today().strftime("%Y-%m-%d")
    out = []

    for r in api_rows:
        subject_id = get_any(r, ["subjectID", "subject_id", "subjectId", "id"])
        subject_name = get_any(r, ["subjectName", "subject_name", "name"])
        parent_id = get_any(r, ["parentID", "parent_id", "parentId"])
        parent_name = get_any(r, ["parentName", "parent_name", "parent"])

        subject_name = str(subject_name or "").strip()
        parent_name = str(parent_name or "").strip()

        if not subject_name:
            continue

        category = f"{parent_name} / {subject_name}" if parent_name else subject_name
        product_type = subject_name

        for field in FEE_FIELDS:
            fee = as_float(r.get(field))
            if fee is None:
                continue

            out.append({
                "marketplace": MARKETPLACE,
                "category": category,
                "product_type": product_type,
                "scheme": SCHEME_LABELS.get(field, field),
                "fee_percent": fee,
                "fee_type": FEE_TYPE,
                "valid_from": valid_from,
                "source_file": SOURCE_FILE,
                "source_note": f"parentID={parent_id}; subjectID={subject_id}; api_field={field}",
                "created_at": now,
                "product_type_norm": norm_text(product_type),
                "category_norm": norm_text(category),
            })

    return out

def table_columns(cur, table: str) -> List[str]:
    return [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]

def main():
    if not DB_PATH.exists():
        raise RuntimeError(f"DB not found: {DB_PATH}")

    api_rows = load_api_rows()
    clean_rows = build_clean_rows(api_rows)

    print(f"WB API rows parsed: {len(api_rows)}")
    print(f"WB clean_commissions rows prepared: {len(clean_rows)}")

    if len(api_rows) < 1000:
        raise RuntimeError(f"Too few WB API rows parsed: {len(api_rows)}")

    if len(clean_rows) < 5000:
        raise RuntimeError(f"Too few clean rows prepared: {len(clean_rows)}")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cols = table_columns(cur, "clean_commissions")
    if not cols:
        raise RuntimeError("Table clean_commissions not found or has no columns")

    insert_cols = [c for c in cols if c != "id" and c in clean_rows[0]]

    required = {"marketplace", "category", "product_type", "scheme", "fee_percent", "fee_type"}
    missing = required - set(insert_cols)
    if missing:
        raise RuntimeError(f"Required columns missing in clean_commissions insert set: {sorted(missing)}")

    old_count = cur.execute(
        "SELECT COUNT(*) FROM clean_commissions WHERE marketplace=? AND fee_type=?",
        (MARKETPLACE, FEE_TYPE),
    ).fetchone()[0]

    print(f"Old WB clean_commissions rows: {old_count}")

    if old_count and len(clean_rows) < int(old_count * 0.7):
        raise RuntimeError(
            f"Prepared rows suspiciously lower than old rows: new={len(clean_rows)}, old={old_count}"
        )

    placeholders = ",".join(["?"] * len(insert_cols))
    col_sql = ",".join(insert_cols)

    values = [
        tuple(row.get(c) for c in insert_cols)
        for row in clean_rows
    ]

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

    print(f"OK: replaced WB clean_commissions rows: {len(clean_rows)}")
    print(f"source_file={SOURCE_FILE}")

if __name__ == "__main__":
    main()
