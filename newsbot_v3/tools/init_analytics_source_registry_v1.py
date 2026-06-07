#!/usr/bin/env python3
"""Idempotently create and seed analytics_source_registry."""

import argparse
import sqlite3
from pathlib import Path

LAYERS = ("news_signal", "official_signal", "legal_official", "tariff_official", "analytics_periodic", "docobrazec_base", "offer_doctor_base", "internal_rule")
TYPES = ("tg", "media", "official", "official_api", "official_excel", "official_pdf", "github_doc", "internal_rule", "manual_file")
SEEDS = [
    ("wb_tariff_official_api_docs", "WB official/API tariff docs", "official_api", None, "wildberries", "tariffs, commissions", "tariff_official", "high", "tariff_docs", "planned", "api/manual", "Planned only; calculations use unified_tariffs.db."),
    ("yandex_market_tariff_official_api_docs", "Yandex Market official/API tariff docs", "official_api", None, "yandex_market", "tariffs, commissions", "tariff_official", "high", "tariff_docs", "planned", "api/manual", "Planned only; calculations use unified_tariffs.db."),
    ("ozon_tariff_official_excel_pdf_manual", "Ozon official Excel/PDF/manual upload", "official_excel", None, "ozon", "tariffs, commissions", "tariff_official", "high", "tariff_docs", "planned", "manual", "Official files/manual upload; calculations use unified_tariffs.db."),
    ("marketplace_legal_docobrazec_official_docs", "Marketplace legal/docs for Docobrazec", "github_doc", None, "multiple", "legal templates and platform rules", "legal_official", "high", "legal_docs", "planned", "manual/github_doc", "Context for Docobrazec; not a tariff source."),
    ("offerdoctor_internal_rules", "OfferDoctor internal rules", "internal_rule", None, "multiple", "offer diagnostics and seller risk rules", "offer_doctor_base", "medium/high", "internal_rules", "planned", "manual", "Internal rules; do not override official docs."),
    ("analytics_periodic_generated_reports", "Analytics periodic generated reports", "internal_rule", None, "multiple", "generated 7/30 day and quarterly analytics", "analytics_periodic", "medium/high", "analytics_report", "planned", "generated", "Generated analytics drafts/reports."),
]


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
    conn.executemany("""
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
    """, SEEDS)
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
