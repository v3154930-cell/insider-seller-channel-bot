#!/usr/bin/env python3
"""Ingest official-source documents into the RAG store.

The tool is intentionally conservative: dry-runs fetch and normalize sources, but
never write rows; fetch failures are reported per source so a batch can still be
reviewed by humans before any real ingestion.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import socket
import sqlite3
import ssl
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib import error, request

OFFICIAL_RAG_LAYERS = (
    "official_signal",
    "legal_official",
    "tariff_official",
    "marketplace_offer",
    "docobrazec_base",
    "offer_doctor_base",
)

SUPPORTED_CONTENT_TYPES = (
    "text/html",
    "application/xhtml+xml",
    "text/plain",
    "application/json",
)

USER_AGENT = "InsiderSellerOfficialRagIngest/1.0 (+manual dry-run)"


@dataclass(frozen=True)
class Source:
    source_key: str
    source_name: str
    source_url: str
    source_type: str
    marketplace: str
    product_scope: str
    rag_layer: str
    trust_level: str
    document_type: str


@dataclass(frozen=True)
class FetchResult:
    url: str
    content_type: str
    body: bytes


class FetchError(Exception):
    def __init__(self, message: str, error_type: str):
        super().__init__(message)
        self.error_type = error_type


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001 - stdlib callback signature
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag.lower() in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag.lower() in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self._parts).split())


def base_dir() -> Path:
    opt = Path("/opt/newsbot_v2")
    return opt if opt.exists() else Path(__file__).resolve().parents[2] / "newsbot_v2"


def default_db() -> Path:
    return base_dir() / "data" / "rag_store.db"


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def _as_source(row: sqlite3.Row) -> Source:
    return Source(
        source_key=row["source_key"],
        source_name=row["source_name"],
        source_url=row["source_url"],
        source_type=row["source_type"],
        marketplace=row["marketplace"] or "unknown",
        product_scope=row["product_scope"] or "",
        rag_layer=row["rag_layer"],
        trust_level=row["trust_level"] or "high",
        document_type=row["document_type"] or "official_document",
    )


def load_sources(
    conn: sqlite3.Connection,
    *,
    source_key: str | None = None,
    layer: str | None = None,
    limit: int | None = None,
) -> list[Source]:
    if not _table_exists(conn, "analytics_source_registry"):
        raise SystemExit("analytics_source_registry table is missing; run init_analytics_source_registry_v1.py first")

    where = ["source_url IS NOT NULL", "TRIM(source_url) != ''"]
    params: list[object] = []
    if source_key:
        where.append("source_key = ?")
        params.append(source_key)
    if layer:
        where.append("rag_layer = ?")
        params.append(layer)
    else:
        where.append("(source_type LIKE 'official%' OR rag_layer IN (" + ",".join("?" for _ in OFFICIAL_RAG_LAYERS) + "))")
        params.extend(OFFICIAL_RAG_LAYERS)

    sql = """
        SELECT source_key, source_name, source_type, source_url, marketplace,
               product_scope, rag_layer, trust_level, document_type
        FROM analytics_source_registry
        WHERE %s
        ORDER BY source_key
    """ % " AND ".join(where)
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return [_as_source(row) for row in conn.execute(sql, params)]


def classify_fetch_exception(exc: BaseException) -> str:
    if isinstance(exc, error.HTTPError):
        if exc.code in {301, 302, 303, 307, 308} and "redirect" in str(exc).lower():
            return "redirect_loop"
        if exc.code == 307:
            return "redirect_loop"
        return "http_error"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exc, error.URLError):
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return "timeout"
        reason_text = str(reason).lower()
        if "timed out" in reason_text or "timeout" in reason_text:
            return "timeout"
        if "redirect" in reason_text and ("loop" in reason_text or "infinite" in reason_text):
            return "redirect_loop"
    return "fetch_error"


def fetch_url(url: str, *, timeout: float, max_bytes: int) -> FetchResult:
    req = request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,application/json;q=0.8,*/*;q=0.1"})
    try:
        context = ssl.create_default_context()
        with request.urlopen(req, timeout=timeout, context=context) as resp:
            content_type = (resp.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if content_type and content_type not in SUPPORTED_CONTENT_TYPES:
                raise FetchError(f"unsupported content type: {content_type}", "unsupported_content_type")
            body = resp.read(max_bytes + 1)
            if len(body) > max_bytes:
                body = body[:max_bytes]
            return FetchResult(url=getattr(resp, "url", url), content_type=content_type or "text/html", body=body)
    except FetchError:
        raise
    except Exception as exc:  # expected network/HTTP errors are classified for one-line output
        raise FetchError(str(exc), classify_fetch_exception(exc)) from exc


def extract_clean_text(body: bytes, content_type: str) -> str:
    text = body.decode("utf-8", errors="replace")
    if content_type in {"text/plain", "application/json"}:
        return " ".join(html.unescape(text).split())
    parser = _TextExtractor()
    parser.feed(text)
    clean = parser.text()
    if not clean:
        text_without_hidden = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        clean = re.sub(r"<[^>]+>", " ", text_without_hidden)
        clean = " ".join(html.unescape(clean).split())
    return clean


def find_title(body: bytes, content_type: str, fallback: str) -> str:
    if content_type not in {"text/html", "application/xhtml+xml"}:
        return fallback
    text = body.decode("utf-8", errors="replace")
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return fallback
    title = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", match.group(1))).split())
    return title or fallback


def has_duplicate_source_url(conn: sqlite3.Connection, source_url: str) -> bool:
    rag_doc_cols = _columns(conn, "rag_documents")
    if "source_url" in rag_doc_cols:
        row = conn.execute("SELECT 1 FROM rag_documents WHERE source_url=? LIMIT 1", (source_url,)).fetchone()
        if row:
            return True
    if _table_exists(conn, "rag_sources"):
        cols = _columns(conn, "rag_sources")
        if "source_url" in cols:
            row = conn.execute("SELECT 1 FROM rag_sources WHERE source_url=? LIMIT 1", (source_url,)).fetchone()
            if row:
                return True
    return False


def insert_document(conn: sqlite3.Connection, source: Source, *, title: str, clean_text: str, content_hash: str) -> None:
    if not clean_text.strip():
        raise ValueError("refusing to insert empty clean_text")

    source_id = None
    if _table_exists(conn, "rag_sources"):
        source_cols = _columns(conn, "rag_sources")
        insert_cols = [c for c in ("source_name", "source_url", "status") if c in source_cols]
        if insert_cols:
            values = [source.source_name if c == "source_name" else source.source_url if c == "source_url" else "active" for c in insert_cols]
            placeholders = ",".join("?" for _ in insert_cols)
            conn.execute(f"INSERT INTO rag_sources ({','.join(insert_cols)}) VALUES ({placeholders})", values)
            source_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    doc_cols = _columns(conn, "rag_documents")
    if not doc_cols:
        raise sqlite3.OperationalError("rag_documents table is missing")

    values_by_col = {
        "source_id": source_id,
        "external_id": source.source_key,
        "source_key": source.source_key,
        "source_name": source.source_name,
        "source_url": source.source_url,
        "title": title,
        "body": clean_text,
        "clean_text": clean_text,
        "content_hash": content_hash,
        "source_type": source.source_type,
        "marketplace": source.marketplace,
        "rag_layer": source.rag_layer,
        "trust_level": source.trust_level,
        "document_type": source.document_type,
    }
    insert_cols = [col for col in values_by_col if col in doc_cols and values_by_col[col] is not None]
    placeholders = ",".join("?" for _ in insert_cols)
    conn.execute(f"INSERT INTO rag_documents ({','.join(insert_cols)}) VALUES ({placeholders})", [values_by_col[c] for c in insert_cols])
    conn.commit()


def process_source(conn: sqlite3.Connection, source: Source, *, dry_run: bool, timeout: float, max_bytes: int) -> dict[str, object]:
    base: dict[str, object] = {
        "source_key": source.source_key,
        "url": source.source_url,
        "layer": source.rag_layer,
        "status": "error",
        "error_type": "",
        "title": "",
        "clean_text_len": 0,
        "content_hash": "",
        "result": "",
    }
    try:
        fetched = fetch_url(source.source_url, timeout=timeout, max_bytes=max_bytes)
        clean_text = extract_clean_text(fetched.body, fetched.content_type)
        title = find_title(fetched.body, fetched.content_type, source.source_name)
        base["title"] = title
        base["clean_text_len"] = len(clean_text)

        if not clean_text.strip():
            base.update(status="skipped", result="empty_clean_text")
            return base

        content_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
        base["content_hash"] = content_hash

        if has_duplicate_source_url(conn, source.source_url):
            base.update(status="skipped", result="duplicate_source_url")
            return base

        if dry_run:
            base.update(status="dry_run", result="would_insert")
            return base

        insert_document(conn, source, title=title, clean_text=clean_text, content_hash=content_hash)
        base.update(status="inserted", result="inserted")
        return base
    except FetchError as exc:
        base.update(status="error", error_type=exc.error_type, result=str(exc))
        return base


def format_result(result: dict[str, object]) -> str:
    keys = ("source_key", "url", "layer", "status", "error_type", "title", "clean_text_len", "content_hash", "result")
    return " | ".join(f"{key}={str(result.get(key, '')).replace(chr(10), ' ').replace(chr(13), ' ')}" for key in keys)


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(default_db()))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--source-key")
    ap.add_argument("--layer")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--max-bytes", type=int, default=1_000_000)
    args = ap.parse_args(list(argv) if argv is not None else None)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        sources = load_sources(conn, source_key=args.source_key, layer=args.layer, limit=args.limit)
        for source in sources:
            result = process_source(conn, source, dry_run=args.dry_run, timeout=args.timeout, max_bytes=args.max_bytes)
            print(format_result(result))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
