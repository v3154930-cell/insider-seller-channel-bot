#!/usr/bin/env python3
"""Ingest official source pages into rag_documents with deterministic quality gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import sqlite3
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib import error, request

DEFAULT_MIN_CLEAN_TEXT_CHARS = 500
SUPPORTED_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml+xml", "application/json")
GENERIC_TITLES = {
    "",
    "wildberries",
    "ozon",
    "яндекс маркет",
    "yandex market",
    "marketplace",
    "official",
    "official regulation project portal",
}


@dataclass(frozen=True)
class OfficialSource:
    source_key: str
    source_name: str
    source_url: str
    source_type: str = "official"
    marketplace: str = "unknown"
    rag_layer: str = "official_signal"
    trust_level: str = "high"
    document_type: str = "official_page"


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "template"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        if self._skip_depth == 0:
            self.parts.append(text)

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @property
    def title(self) -> str:
        return self._clean(" ".join(self.title_parts))

    @property
    def clean_text(self) -> str:
        return self._clean(" ".join(self.parts))


def base_dir() -> Path:
    opt = Path("/opt/newsbot_v2")
    return opt if opt.exists() else Path(__file__).resolve().parents[2] / "newsbot_v2"


def default_db() -> Path:
    return base_dir() / "data" / "rag_store.db"


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute("PRAGMA table_info(%s)" % q(table))}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def extract_html(html: str) -> tuple[str, str]:
    parser = TextExtractor()
    parser.feed(html)
    return parser.title, parser.clean_text


def has_mojibake(text: str) -> bool:
    if not text:
        return False
    replacement_count = text.count("\ufffd")
    if replacement_count == 0:
        return False
    if re.search("\ufffd{4,}", text):
        return True
    return replacement_count >= 3 and (replacement_count / max(len(text), 1)) >= 0.005


def is_generic_title(title: str) -> bool:
    normalized = normalize_text(title).casefold()
    normalized = re.sub(r"[\W_]+", " ", normalized, flags=re.UNICODE).strip()
    return normalized in GENERIC_TITLES


def skipped_result(source: OfficialSource, error_type: str, clean_text: str = "", title: str = "", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "source_key": source.source_key,
        "source_url": source.source_url,
        "title": title,
        "status": "skipped",
        "error_type": error_type,
        "content_hash": "",
        "result": error_type,
        "clean_text_len": len(clean_text or ""),
    }
    if extra:
        row.update(extra)
    return row


def error_result(source: OfficialSource, error_type: str, message: str) -> dict[str, Any]:
    return {
        "source_key": source.source_key,
        "source_url": source.source_url,
        "title": "",
        "status": "error",
        "error_type": error_type,
        "content_hash": "",
        "result": error_type,
        "clean_text_len": 0,
        "error": message,
    }


def process_extracted_document(
    source: OfficialSource,
    *,
    title: str,
    clean_text: str,
    min_clean_text_chars: int = DEFAULT_MIN_CLEAN_TEXT_CHARS,
    dry_run: bool = True,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    title = normalize_text(title) or source.source_name
    clean_text = normalize_text(clean_text)

    if has_mojibake(title) or has_mojibake(clean_text):
        return skipped_result(source, "mojibake_detected", clean_text=clean_text, title=title)

    if len(clean_text) < min_clean_text_chars:
        return skipped_result(
            source,
            "too_short_clean_text",
            clean_text=clean_text,
            title=title,
            extra={"generic_title": is_generic_title(title)},
        )

    content_hash = hashlib.sha256((source.source_url + "\n" + clean_text).encode("utf-8")).hexdigest()
    row = {
        "source_key": source.source_key,
        "source_url": source.source_url,
        "title": title,
        "status": "dry_run" if dry_run else "inserted",
        "error_type": "",
        "content_hash": content_hash,
        "result": "would_insert" if dry_run else "inserted",
        "clean_text_len": len(clean_text),
    }
    if not dry_run:
        if conn is None:
            raise ValueError("conn is required when dry_run=False")
        insert_document(conn, source, title=title, clean_text=clean_text, content_hash=content_hash)
    return row


def fetch_url(url: str, timeout_seconds: int) -> tuple[str, str]:
    req = request.Request(url, headers={"User-Agent": "Mozilla/5.0 compatible; InsiderSellerBot/1.0"})
    context = ssl.create_default_context()
    with request.urlopen(req, timeout=timeout_seconds, context=context) as response:
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type and content_type not in SUPPORTED_CONTENT_TYPES:
            raise ValueError("unsupported_content_type:%s" % content_type)
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace"), content_type


def load_sources(conn: sqlite3.Connection) -> list[OfficialSource]:
    conn.row_factory = sqlite3.Row
    sources: list[OfficialSource] = []
    if table_exists(conn, "analytics_source_registry"):
        cols = columns(conn, "analytics_source_registry")
        if {"source_key", "source_name", "source_url"}.issubset(cols):
            where = "source_url IS NOT NULL AND TRIM(source_url) != ''"
            if "source_type" in cols:
                where += " AND source_type LIKE 'official%'"
            if "ingest_status" in cols:
                where += " AND COALESCE(ingest_status, '') NOT IN ('disabled', 'blocked')"
            for row in conn.execute("SELECT * FROM analytics_source_registry WHERE %s ORDER BY id" % where):
                sources.append(
                    OfficialSource(
                        source_key=row["source_key"],
                        source_name=row["source_name"],
                        source_url=row["source_url"],
                        source_type=row["source_type"] if "source_type" in row.keys() else "official",
                        marketplace=row["marketplace"] if "marketplace" in row.keys() else "unknown",
                        rag_layer=row["rag_layer"] if "rag_layer" in row.keys() else "official_signal",
                        trust_level=row["trust_level"] if "trust_level" in row.keys() else "high",
                        document_type=row["document_type"] if "document_type" in row.keys() else "official_page",
                    )
                )
    if sources or not table_exists(conn, "rag_sources"):
        return sources
    rag_source_cols = columns(conn, "rag_sources")
    rag_where = "COALESCE(enabled, 1)=1" if "enabled" in rag_source_cols else "1=1"
    for row in conn.execute("SELECT * FROM rag_sources WHERE %s ORDER BY id" % rag_where):
        keys = row.keys()
        source_url = row["url"] if "url" in keys else row["source_url"] if "source_url" in keys else ""
        if not source_url:
            continue
        sources.append(
            OfficialSource(
                source_key=row["source_key"] if "source_key" in keys else str(row["id"]),
                source_name=row["name"] if "name" in keys else row["source_name"] if "source_name" in keys else str(row["id"]),
                source_url=source_url,
                source_type=row["source_type"] if "source_type" in keys else "official",
                marketplace=row["marketplace"] if "marketplace" in keys else "unknown",
                rag_layer=row["rag_layer"] if "rag_layer" in keys else "official_signal",
                trust_level=row["trust_level"] if "trust_level" in keys else "high",
                document_type=row["document_type"] if "document_type" in keys else "official_page",
            )
        )
    return sources


def source_url_exists(conn: sqlite3.Connection, source_url: str) -> bool:
    if not table_exists(conn, "rag_documents"):
        return False
    cols = columns(conn, "rag_documents")
    for col in ("source_url", "link"):
        if col in cols and conn.execute("SELECT 1 FROM rag_documents WHERE %s=? LIMIT 1" % q(col), (source_url,)).fetchone():
            return True
    return False


def insert_document(conn: sqlite3.Connection, source: OfficialSource, *, title: str, clean_text: str, content_hash: str) -> None:
    if not table_exists(conn, "rag_documents"):
        conn.execute(
            """
            CREATE TABLE rag_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                clean_text TEXT,
                markdown_text TEXT,
                source TEXT,
                source_type TEXT,
                marketplace TEXT,
                document_type TEXT,
                topic TEXT,
                impact_level TEXT,
                published_at TEXT,
                link TEXT,
                content_hash TEXT UNIQUE,
                rag_eligible INTEGER DEFAULT 1,
                eligibility_reason TEXT,
                rag_layer TEXT,
                trust_level TEXT,
                source_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    cols = columns(conn, "rag_documents")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    values = {
        "title": title,
        "clean_text": clean_text,
        "markdown_text": clean_text,
        "body": clean_text,
        "source": source.source_name,
        "source_type": source.source_type,
        "marketplace": source.marketplace,
        "document_type": source.document_type,
        "topic": "official",
        "impact_level": "high",
        "published_at": now,
        "link": source.source_url,
        "source_url": source.source_url,
        "content_hash": content_hash,
        "rag_eligible": 1,
        "eligibility_reason": "official source imported after quality gates",
        "rag_layer": source.rag_layer,
        "trust_level": source.trust_level,
        "created_at": now,
    }
    insert_cols = [col for col in values if col in cols]
    placeholders = ", ".join("?" for _ in insert_cols)
    sql = "INSERT INTO rag_documents (%s) VALUES (%s)" % (", ".join(q(c) for c in insert_cols), placeholders)
    conn.execute(sql, [values[c] for c in insert_cols])
    conn.commit()


def process_source(conn: sqlite3.Connection, source: OfficialSource, *, dry_run: bool, min_clean_text_chars: int, timeout_seconds: int) -> dict[str, Any]:
    if source_url_exists(conn, source.source_url):
        return skipped_result(source, "duplicate_source_url")
    try:
        payload, content_type = fetch_url(source.source_url, timeout_seconds)
    except error.HTTPError as exc:
        if 300 <= getattr(exc, "code", 0) < 400:
            return error_result(source, "redirect_loop", "HTTP %s" % exc.code)
        return error_result(source, "http_error", "HTTP %s" % exc.code)
    except error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        if "redirect" in reason.lower():
            return error_result(source, "redirect_loop", reason)
        if "timed out" in reason.lower() or isinstance(getattr(exc, "reason", None), socket.timeout):
            return error_result(source, "timeout", reason)
        return error_result(source, "fetch_error", reason)
    except socket.timeout as exc:
        return error_result(source, "timeout", str(exc))
    except TimeoutError as exc:
        return error_result(source, "timeout", str(exc))
    except ValueError as exc:
        if str(exc).startswith("unsupported_content_type:"):
            return error_result(source, "unsupported_content_type", str(exc).split(":", 1)[1])
        return error_result(source, "fetch_error", str(exc))

    if content_type == "text/plain":
        title, clean_text = source.source_name, payload
    elif content_type == "application/json":
        title, clean_text = source.source_name, json.dumps(json.loads(payload), ensure_ascii=False, sort_keys=True)
    else:
        title, clean_text = extract_html(payload)
        title = title or source.source_name
    return process_extracted_document(
        source,
        title=title,
        clean_text=clean_text,
        min_clean_text_chars=min_clean_text_chars,
        dry_run=dry_run,
        conn=conn,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest official RAG sources with text quality gates")
    ap.add_argument("--db", default=str(default_db()))
    ap.add_argument("--dry-run", action="store_true", help="Fetch and validate sources without inserting rag_documents")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout-seconds", type=int, default=20)
    ap.add_argument("--min-clean-text-chars", type=int, default=DEFAULT_MIN_CLEAN_TEXT_CHARS)
    args = ap.parse_args()

    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    sources = load_sources(conn)
    if args.limit > 0:
        sources = sources[: args.limit]
    for source in sources:
        result = process_source(
            conn,
            source,
            dry_run=args.dry_run,
            min_clean_text_chars=args.min_clean_text_chars,
            timeout_seconds=args.timeout_seconds,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
