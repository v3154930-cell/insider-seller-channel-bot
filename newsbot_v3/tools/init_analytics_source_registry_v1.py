#!/usr/bin/env python3
"""Idempotently create and seed analytics_source_registry."""

import argparse
import json
import sqlite3
from pathlib import Path

LAYERS = (
    "news_signal",
    "official_signal",
    "legal_official",
    "marketplace_offer",
    "tariff_official",
    "compliance_official",
    "tax_official",
    "seller_templates",
    "analytics_periodic",
    "docobrazec_base",
    "offer_doctor_base",
    "internal_rule",
)
TYPES = (
    "tg",
    "media",
    "official",
    "official_html",
    "official_api",
    "official_excel",
    "official_pdf",
    "github_doc",
    "internal_rule",
    "manual_file",
)
SEEDS = [
    ("wb_tariff_official_api_docs", "WB official/API tariff docs", "official_api", None, "wildberries", "tariffs, commissions", "tariff_official", "high", "tariff_docs", "planned", "api/manual", "Planned only; calculations use unified_tariffs.db."),
    ("yandex_market_tariff_official_api_docs", "Yandex Market official/API tariff docs", "official_api", None, "yandex_market", "tariffs, commissions", "tariff_official", "high", "tariff_docs", "planned", "api/manual", "Planned only; calculations use unified_tariffs.db."),
    ("ozon_tariff_official_excel_pdf_manual", "Ozon official Excel/PDF/manual upload", "official_excel", None, "ozon", "tariffs, commissions", "tariff_official", "high", "tariff_docs", "planned", "manual", "Official files/manual upload; calculations use unified_tariffs.db."),
    ("marketplace_legal_docobrazec_official_docs", "Marketplace legal/docs for Docobrazec", "github_doc", None, "multiple", "legal templates and platform rules", "legal_official", "high", "legal_docs", "planned", "manual/github_doc", "Context for Docobrazec; not a tariff source."),
    ("offerdoctor_internal_rules", "OfferDoctor internal rules", "internal_rule", None, "multiple", "offer diagnostics and seller risk rules", "offer_doctor_base", "medium/high", "internal_rules", "planned", "manual", "Internal rules; do not override official docs."),
    ("analytics_periodic_generated_reports", "Analytics periodic generated reports", "internal_rule", None, "multiple", "generated 7/30 day and quarterly analytics", "analytics_periodic", "medium/high", "analytics_report", "planned", "generated", "Generated analytics drafts/reports."),
    ("seller_templates_manual_foundation", "Seller templates manual foundation", "manual_file", None, "multiple", "seller templates and safe examples", "seller_templates", "medium/high", "seller_templates", "planned", "manual", "Template corpus for future Docobrazec/Seller Helper RAG; official/public materials only."),
]

# Production rag_store.db may already have analytics_source_registry with the
# original v1 CHECK constraints.  We do not run destructive migrations here; if
# a newer conceptual layer/type is rejected by an existing table, the seed falls
# back to the closest layer/type that v1 already used and records the requested
# value in notes.  Fresh databases still get the extended CHECK list above.
LEGACY_LAYER_FALLBACKS = {
    "marketplace_offer": "official_signal",
    "compliance_official": "legal_official",
    "tax_official": "legal_official",
    "seller_templates": "docobrazec_base",
}
LEGACY_TYPE_FALLBACKS = {
    "official_html": "official",
}


def with_legacy_registry_fallback(row):
    values = list(row)
    original_type = values[2]
    original_layer = values[6]
    fallback_type = LEGACY_TYPE_FALLBACKS.get(original_type, original_type)
    fallback_layer = LEGACY_LAYER_FALLBACKS.get(original_layer, original_layer)
    if fallback_type == original_type and fallback_layer == original_layer:
        return None
    values[2] = fallback_type
    values[6] = fallback_layer
    suffix_parts = []
    if fallback_type != original_type:
        suffix_parts.append("requested_source_type=%s" % original_type)
    if fallback_layer != original_layer:
        suffix_parts.append("requested_rag_layer=%s" % original_layer)
    values[11] = (str(values[11] or "") + " Registry compatibility fallback: " + "; ".join(suffix_parts) + ".").strip()
    return tuple(values)


def official_seed_path():
    return Path(__file__).resolve().parents[1] / "config" / "official_rag_sources_v1.json"


def load_official_rag_source_seeds(path=None):
    path = Path(path) if path else official_seed_path()
    if not path.exists():
        return []
    rows = []
    for item in json.loads(path.read_text(encoding="utf-8")):
        layer = str(item["rag_layer"])
        if layer not in LAYERS:
            raise ValueError("Unsupported rag_layer in %s: %s" % (item.get("source_key"), layer))
        source_type = str(item.get("source_type") or "official_html")
        if source_type not in TYPES:
            raise ValueError("Unsupported source_type in %s: %s" % (item.get("source_key"), source_type))
        rows.append((
            str(item["source_key"]),
            str(item["source_name"]),
            source_type,
            str(item["source_url"]),
            str(item.get("marketplace") or "unknown"),
            "official/public RAG source",
            layer,
            str(item.get("trust_level") or "high"),
            layer,
            "planned",
            str(item.get("refresh_policy") or "manual_dry_run_first"),
            str(item.get("notes") or ""),
        ))
    return rows


def base_dir():
    opt = Path("/opt/newsbot_v2")
    return opt if opt.exists() else Path(__file__).resolve().parents[2] / "newsbot_v2"


def default_db():
    return base_dir() / "data" / "rag_store.db"


def create(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS analytics_source_registry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_key TEXT UNIQUE NOT NULL,
        source_name TEXT NOT NULL,
        source_type TEXT NOT NULL CHECK(source_type IN (%s)),
        source_url TEXT,
        marketplace TEXT DEFAULT 'unknown',
        product_scope TEXT,
        rag_layer TEXT NOT NULL CHECK(rag_layer IN (%s)),
        trust_level TEXT NOT NULL,
        document_type TEXT,
        ingest_status TEXT DEFAULT 'planned',
        refresh_mode TEXT DEFAULT 'manual',
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """ % (", ".join("'%s'" % x for x in TYPES), ", ".join("'%s'" % x for x in LAYERS)))
    conn.commit()


def seed(conn):
    sql = """
    INSERT INTO analytics_source_registry (
        source_key, source_name, source_type, source_url, marketplace,
        product_scope, rag_layer, trust_level, document_type, ingest_status,
        refresh_mode, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(source_key) DO UPDATE SET
        source_name=excluded.source_name,
        source_type=excluded.source_type,
        source_url=excluded.source_url,
        marketplace=excluded.marketplace,
        product_scope=excluded.product_scope,
        rag_layer=excluded.rag_layer,
        trust_level=excluded.trust_level,
        document_type=excluded.document_type,
        ingest_status=excluded.ingest_status,
        refresh_mode=excluded.refresh_mode,
        notes=excluded.notes,
        updated_at=CURRENT_TIMESTAMP
    """
    for row in list(SEEDS) + load_official_rag_source_seeds():
        try:
            conn.execute(sql, row)
        except sqlite3.IntegrityError as exc:
            fallback = with_legacy_registry_fallback(row)
            if not fallback:
                print("analytics_source_registry_seed_skipped source_key=%s reason=%s" % (row[0], exc))
                continue
            try:
                conn.execute(sql, fallback)
                print(
                    "analytics_source_registry_seed_fallback source_key=%s rag_layer=%s source_type=%s"
                    % (fallback[0], fallback[6], fallback[2])
                )
            except sqlite3.IntegrityError as fallback_exc:
                print("analytics_source_registry_seed_skipped source_key=%s reason=%s" % (row[0], fallback_exc))
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(default_db()))
    args = ap.parse_args()
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    create(conn)
    seed(conn)
    print("analytics_source_registry=ready rows=%s" % conn.execute("SELECT COUNT(*) FROM analytics_source_registry").fetchone()[0])
    conn.close()
    print("analytics_source_registry_db=%s" % db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
