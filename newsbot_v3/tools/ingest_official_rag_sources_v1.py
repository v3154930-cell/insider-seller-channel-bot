#!/usr/bin/env python3
"""Ingest official registry sources into rag_store.db with conservative gates."""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib import error, request

TEXT_CONTENT_TYPES = (
    "text/",
    "application/json",
    "application/xml",
    "application/rss+xml",
    "application/xhtml+xml",
    "application/pdf",
)

MOJIBAKE_MARKERS = ("�", "Р°", "Рµ", "Рё", "Ро", "Рћ", "СЃ", "С‚", "Ð", "Ñ")


@dataclass(frozen=True)
class RegistrySource:
    source_key: str
    source_name: str
    source_url: str
    source_type: str
    marketplace: str
    rag_layer: str
    trust_level: str
    document_type: str


@dataclass(frozen=True)
class FetchResult:
    status: str
    final_url: str
    content_type: str
    body: bytes


def base_dir() -> Path:
    opt = Path("/opt/newsbot_v2")
    return opt if opt.exists() else Path(__file__).resolve().parents[2] / "newsbot_v2"


def default_db() -> Path:
    return base_dir() / "data" / "rag_store.db"


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute("PRAGMA table_info(%s)" % q(table))]


def ensure_rag_documents(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_documents (
            id INTEGER PRIMARY KEY,
            source_id INTEGER,
            external_id TEXT,
            title TEXT,
            body TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    existing = set(columns(conn, "rag_documents"))
    additions = {
        "source": "TEXT",
        "source_key": "TEXT",
        "source_url": "TEXT",
        "raw_text": "TEXT",
        "clean_text": "TEXT",
        "content_hash": "TEXT",
        "rag_layer": "TEXT",
        "source_type": "TEXT",
        "marketplace": "TEXT",
        "trust_level": "TEXT",
        "document_type": "TEXT",
        "ingest_status": "TEXT",
        "skip_reason": "TEXT",
        "error_reason": "TEXT",
    }
    for name, decl in additions.items():
        if name not in existing:
            conn.execute("ALTER TABLE rag_documents ADD COLUMN %s %s" % (q(name), decl))
    conn.commit()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest official RAG sources from analytics_source_registry")
    parser.add_argument("--db", default=str(default_db()))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--min-clean-text-chars", type=int, default=500)
    parser.add_argument("--source-key", help="Filter registry to exactly one source_key before ingestion")
    parser.add_argument("--layer", help="Filter registry sources by effective/conceptual RAG layer")
    return parser.parse_args(argv)


def load_registry_sources(conn: sqlite3.Connection) -> list[RegistrySource]:
    if not table_exists(conn, "analytics_source_registry"):
        raise ValueError("analytics_source_registry table is missing")
    cols = set(columns(conn, "analytics_source_registry"))
    layer_expr = "rag_layer" if "rag_layer" in cols else "layer" if "layer" in cols else "''"
    rows = conn.execute(
        """
        SELECT
            source_key,
            COALESCE(source_name, source_key) AS source_name,
            COALESCE(source_url, '') AS source_url,
            COALESCE(source_type, '') AS source_type,
            COALESCE(marketplace, 'unknown') AS marketplace,
            COALESCE(%s, '') AS rag_layer,
            COALESCE(trust_level, '') AS trust_level,
            COALESCE(document_type, '') AS document_type
        FROM analytics_source_registry
        ORDER BY source_key
        """
        % layer_expr
    ).fetchall()
    sources: list[RegistrySource] = []
    for row in rows:
        sources.append(
            RegistrySource(
                source_key=str(row["source_key"] or "").strip(),
                source_name=str(row["source_name"] or "").strip(),
                source_url=str(row["source_url"] or "").strip(),
                source_type=str(row["source_type"] or "").strip(),
                marketplace=str(row["marketplace"] or "unknown").strip(),
                rag_layer=str(row["rag_layer"] or "").strip(),
                trust_level=str(row["trust_level"] or "").strip(),
                document_type=str(row["document_type"] or "").strip(),
            )
        )
    return sources


def apply_filters(sources: list[RegistrySource], source_key: str | None, layer: str | None) -> list[RegistrySource]:
    filtered = sources
    if source_key:
        filtered = [source for source in filtered if source.source_key == source_key]
        if not filtered:
            raise ValueError("source_key not found in analytics_source_registry: %s" % source_key)
    if layer:
        filtered = [source for source in filtered if source.rag_layer == layer]
    return filtered


def is_supported_content_type(content_type: str) -> bool:
    lowered = (content_type or "").split(";", 1)[0].strip().lower()
    return any(lowered.startswith(prefix) for prefix in TEXT_CONTENT_TYPES)


def fetch_url(url: str, timeout_seconds: float) -> FetchResult:
    req = request.Request(url, headers={"User-Agent": "newsbot-official-rag-ingest/1.0"})
    with request.urlopen(req, timeout=timeout_seconds) as resp:
        final_url = getattr(resp, "url", url)
        content_type = resp.headers.get("Content-Type", "")
        body = resp.read()
    return FetchResult(status="ok", final_url=final_url, content_type=content_type, body=body)


def decode_body(body: bytes, content_type: str) -> str:
    match = re.search(r"charset=([^;\s]+)", content_type or "", flags=re.IGNORECASE)
    encodings = [match.group(1)] if match else []
    encodings.extend(["utf-8", "cp1251"])
    for encoding in encodings:
        try:
            return body.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


def clean_text(raw: str, content_type: str = "") -> str:
    text = raw
    if "html" in (content_type or "").lower() or re.search(r"<[^>]+>", text):
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def mojibake_detected(text: str) -> bool:
    if not text:
        return False
    marker_count = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    return marker_count >= 3 or ("�" in text and text.count("�") / max(len(text), 1) > 0.01)


def source_url_exists(conn: sqlite3.Connection, source_url: str) -> bool:
    if not source_url or not table_exists(conn, "rag_documents") or "source_url" not in columns(conn, "rag_documents"):
        return False
    row = conn.execute("SELECT 1 FROM rag_documents WHERE source_url=? AND COALESCE(ingest_status, '')='ingested' LIMIT 1", (source_url,)).fetchone()
    return row is not None


def insert_document(
    conn: sqlite3.Connection,
    source: RegistrySource,
    status: str,
    body: str = "",
    clean: str = "",
    content_hash: str = "",
    skip_reason: str = "",
    error_reason: str = "",
) -> None:
    ensure_rag_documents(conn)
    values = {
        "external_id": source.source_key,
        "title": source.source_name,
        "body": body,
        "source": source.source_name,
        "source_key": source.source_key,
        "source_url": source.source_url,
        "raw_text": body,
        "clean_text": clean,
        "content_hash": content_hash if status == "ingested" else "",
        "rag_layer": source.rag_layer,
        "source_type": source.source_type,
        "marketplace": source.marketplace,
        "trust_level": source.trust_level,
        "document_type": source.document_type,
        "ingest_status": status,
        "skip_reason": skip_reason,
        "error_reason": error_reason,
    }
    keys = [key for key in values if key in columns(conn, "rag_documents")]
    conn.execute(
        "INSERT INTO rag_documents (%s) VALUES (%s)" % (", ".join(q(k) for k in keys), ", ".join("?" for _ in keys)),
        [values[key] for key in keys],
    )
    conn.commit()


def process_source(conn: sqlite3.Connection, source: RegistrySource, args: argparse.Namespace) -> dict[str, str]:
    if not source.source_url:
        if not args.dry_run:
            insert_document(conn, source, "skipped", skip_reason="missing_source_url")
        return {"status": "skipped", "reason": "missing_source_url", "source_key": source.source_key}
    if source_url_exists(conn, source.source_url):
        if not args.dry_run:
            insert_document(conn, source, "skipped", skip_reason="duplicate_source_url")
        return {"status": "skipped", "reason": "duplicate_source_url", "source_key": source.source_key}
    try:
        fetched = fetch_url(source.source_url, args.timeout_seconds)
    except TimeoutError:
        if not args.dry_run:
            insert_document(conn, source, "error", error_reason="timeout")
        return {"status": "dry_run" if args.dry_run else "error", "reason": "timeout", "source_key": source.source_key}
    except error.HTTPError as exc:
        if not args.dry_run:
            insert_document(conn, source, "error", error_reason="http_error")
        return {"status": "dry_run" if args.dry_run else "error", "reason": "http_error", "source_key": source.source_key, "http_status": str(exc.code)}
    except error.URLError as exc:
        reason = "timeout" if "timed out" in str(exc.reason).lower() else "redirect_loop" if "redirect" in str(exc.reason).lower() else "http_error"
        if not args.dry_run:
            insert_document(conn, source, "error", error_reason=reason)
        return {"status": "dry_run" if args.dry_run else "error", "reason": reason, "source_key": source.source_key}
    except Exception as exc:
        reason = "redirect_loop" if "redirect" in str(exc).lower() else "http_error"
        if not args.dry_run:
            insert_document(conn, source, "error", error_reason=reason)
        return {"status": "dry_run" if args.dry_run else "error", "reason": reason, "source_key": source.source_key}

    if not is_supported_content_type(fetched.content_type):
        if not args.dry_run:
            insert_document(conn, source, "skipped", skip_reason="unsupported_content_type")
        return {"status": "dry_run" if args.dry_run else "skipped", "reason": "unsupported_content_type", "source_key": source.source_key}
    raw = decode_body(fetched.body, fetched.content_type)
    cleaned = clean_text(raw, fetched.content_type)
    if len(cleaned) < args.min_clean_text_chars:
        if not args.dry_run:
            insert_document(conn, source, "skipped", body=raw, clean=cleaned, skip_reason="too_short_clean_text")
        return {"status": "dry_run" if args.dry_run else "skipped", "reason": "too_short_clean_text", "source_key": source.source_key}
    if mojibake_detected(cleaned):
        if not args.dry_run:
            insert_document(conn, source, "skipped", body=raw, clean=cleaned, skip_reason="mojibake_detected")
        return {"status": "dry_run" if args.dry_run else "skipped", "reason": "mojibake_detected", "source_key": source.source_key}
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    if not args.dry_run:
        insert_document(conn, source, "ingested", body=raw, clean=cleaned, content_hash=digest)
    return {"status": "dry_run" if args.dry_run else "ingested", "reason": "would_ingest" if args.dry_run else "ok", "source_key": source.source_key, "content_hash": digest}


def iter_limited(sources: Iterable[RegistrySource], limit: int | None) -> list[RegistrySource]:
    items = list(sources)
    if limit is None:
        return items
    return items[: max(limit, 0)]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        sources = load_registry_sources(conn)
        sources = apply_filters(sources, args.source_key, args.layer)
        sources = iter_limited(sources, args.limit)
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        conn.close()
        return 2

    print("official_rag_sources_selected=%s" % len(sources))
    counts: dict[str, int] = {}
    for source in sources:
        result = process_source(conn, source, args)
        counts[result["status"]] = counts.get(result["status"], 0) + 1
        print("source_key=%s status=%s reason=%s" % (result["source_key"], result["status"], result["reason"]))
    print("official_rag_ingest_summary=%s" % ",".join("%s:%s" % (key, counts[key]) for key in sorted(counts)))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
