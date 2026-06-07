#!/usr/bin/env python3
"""Read-only healthcheck for NEWSBOT rag_store.db."""

import argparse
import sqlite3
from pathlib import Path


def base_dir():
    opt = Path("/opt/newsbot_v2")
    return opt if opt.exists() else Path(__file__).resolve().parents[2] / "newsbot_v2"


def default_db():
    return base_dir() / "data" / "rag_store.db"


def q(name):
    return '"' + name.replace('"', '""') + '"'


def table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def columns(conn, table):
    return [r[1] for r in conn.execute("PRAGMA table_info(%s)" % q(table))]


def pick(cols, *names):
    for name in names:
        if name in cols:
            return name
    return None


def count_by(conn, table, col, label):
    print("\n== count by %s ==" % label)
    if not col:
        print("SKIP: missing column")
        return
    sql = """
        SELECT COALESCE(NULLIF(TRIM(%s), ''), '<empty>') AS value, COUNT(*) AS cnt
        FROM %s GROUP BY value ORDER BY cnt DESC, value
    """ % (q(col), q(table))
    for row in conn.execute(sql):
        print("%s: %s" % (row["value"], row["cnt"]))


def print_rows(title, rows):
    print("\n== %s ==" % title)
    seen = False
    for row in rows:
        seen = True
        print(" | ".join("%s=%s" % (k, row[k]) for k in row.keys()))
    if not seen:
        print("none")


def main():
    ap = argparse.ArgumentParser(description="Read-only RAG healthcheck v1")
    ap.add_argument("--db", default=str(default_db()))
    args = ap.parse_args()
    db = Path(args.db)
    print("rag_db=%s" % db)
    if not db.exists():
        print("ERROR: rag_store.db does not exist")
        return 2

    conn = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    conn.row_factory = sqlite3.Row
    print("\n== tables ==")
    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        print(row["name"])
    print("\n== schema ==")
    for row in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"):
        print("\n-- %s --" % row["name"])
        print(row["sql"])
    print("\nrag_sources=%s" % ("present" if table_exists(conn, "rag_sources") else "missing"))
    if not table_exists(conn, "rag_documents"):
        print("\nERROR: rag_documents table is missing")
        conn.close()
        return 2

    cols = columns(conn, "rag_documents")
    print("\n== rag_documents columns ==")
    print(", ".join(cols))
    clean = pick(cols, "clean_text")
    eligible = pick(cols, "rag_eligible", "eligible")
    layer = pick(cols, "rag_layer")
    source_type = pick(cols, "source_type")
    marketplace = pick(cols, "marketplace")
    trust = pick(cols, "trust_level")
    source_url = pick(cols, "source_url", "link", "url")

    total = conn.execute("SELECT COUNT(*) FROM rag_documents").fetchone()[0]
    empty_clean = total
    if clean:
        empty_clean = conn.execute("SELECT COUNT(*) FROM rag_documents WHERE %s IS NULL OR TRIM(%s)=''" % (q(clean), q(clean))).fetchone()[0]
    eligible_docs = total - empty_clean
    if eligible:
        eligible_docs = conn.execute("SELECT COUNT(*) FROM rag_documents WHERE COALESCE(%s, 0)=1" % q(eligible)).fetchone()[0]
    print("\n== totals ==")
    print("total_docs=%s" % total)
    print("empty_clean_text=%s" % empty_clean)
    print("eligible_docs=%s" % eligible_docs)
    count_by(conn, "rag_documents", layer, "rag_layer")
    count_by(conn, "rag_documents", source_type, "source_type")
    count_by(conn, "rag_documents", marketplace, "marketplace")
    count_by(conn, "rag_documents", trust, "trust_level")

    selected = [c for c in ("id", "title", "source", source_type, marketplace, layer, trust, "published_at", "created_at", source_url) if c and c in cols]
    select_sql = ", ".join(q(c) for c in selected)
    print_rows("latest 20 documents", conn.execute("SELECT %s FROM rag_documents ORDER BY id DESC LIMIT 20" % select_sql))

    problems = []
    for col in (clean, source_url, layer, trust):
        if col:
            problems.append("%s IS NULL OR TRIM(%s)=''" % (q(col), q(col)))
    if problems:
        sql = "SELECT %s FROM rag_documents WHERE %s ORDER BY id DESC LIMIT 50" % (select_sql, " OR ".join("(%s)" % p for p in problems))
        print_rows("problematic documents", conn.execute(sql))
    else:
        print("\n== problematic documents ==\nSKIP: no known problem columns")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
