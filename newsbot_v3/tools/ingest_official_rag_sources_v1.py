#!/usr/bin/env python3
"""Dry-run-first ingestion for official/public RAG sources.

This tool is intentionally separate from publisher runtime code.  It fetches
only allowlisted official/public URLs and writes to rag_documents only when
--dry-run is not supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

RAG_LAYERS = (
    "legal_official",
    "marketplace_offer",
    "tariff_official",
    "compliance_official",
    "tax_official",
    "seller_templates",
)

ALLOWED_DOMAINS = frozenset(
    {
        "pravo.gov.ru",
        "regulation.gov.ru",
        "nalog.gov.ru",
        "www.nalog.gov.ru",
        "rospotrebnadzor.ru",
        "www.rospotrebnadzor.ru",
        "fsa.gov.ru",
        "www.fsa.gov.ru",
        "xn--80ajghhoc2aj1c8b.xn--p1ai",
        "честныйзнак.рф",
        "seller.ozon.ru",
        "business.ozon.ru",
        "seller.wildberries.ru",
        "portal.wildberries.ru",
        "yandex.ru",
        "partner.market.yandex.ru",
    }
)

TEXT_CONTENT_TYPES = ("text/html", "text/plain")
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_BYTES = 1_000_000
SEED_PATH = Path(__file__).resolve().parents[1] / "config" / "official_rag_sources_v1.json"


@dataclass(frozen=True)
class OfficialSource:
    source_key: str
    source_name: str
    source_url: str
    source_type: str
    rag_layer: str
    marketplace: str
    trust_level: str
    refresh_policy: str
    notes: str


@dataclass(frozen=True)
class FetchResult:
    url: str
    content_type: str
    body: bytes


def base_dir() -> Path:
    opt = Path("/opt/newsbot_v2")
    return opt if opt.exists() else Path(__file__).resolve().parents[2] / "newsbot_v2"


def default_db() -> Path:
    return base_dir() / "data" / "rag_store.db"


def normalize_host(hostname: str | None) -> str:
    if not hostname:
        return ""
    host = hostname.strip().lower().rstrip(".")
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return host


def is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = normalize_host(parsed.hostname)
    if not host:
        return False
    for domain in ALLOWED_DOMAINS:
        normalized_domain = normalize_host(domain)
        if host == normalized_domain or host.endswith("." + normalized_domain):
            return True
    return False


def load_sources(path: Path = SEED_PATH) -> list[OfficialSource]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    sources: list[OfficialSource] = []
    for item in raw:
        source = OfficialSource(
            source_key=str(item["source_key"]),
            source_name=str(item["source_name"]),
            source_url=str(item["source_url"]),
            source_type=str(item["source_type"]),
            rag_layer=str(item["rag_layer"]),
            marketplace=str(item.get("marketplace") or "unknown"),
            trust_level=str(item.get("trust_level") or "high"),
            refresh_policy=str(item.get("refresh_policy") or "manual_dry_run_first"),
            notes=str(item.get("notes") or ""),
        )
        if source.rag_layer not in RAG_LAYERS:
            raise ValueError(f"Unsupported rag_layer in seed {source.source_key}: {source.rag_layer}")
        sources.append(source)
    return sources


def select_sources(sources: Iterable[OfficialSource], source_key: str | None, layer: str | None, limit: int | None) -> list[OfficialSource]:
    selected = []
    for source in sources:
        if source_key and source.source_key != source_key:
            continue
        if layer and source.rag_layer != layer:
            continue
        selected.append(source)
        if limit is not None and len(selected) >= limit:
            break
    return selected


def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS, max_bytes: int = DEFAULT_MAX_BYTES) -> FetchResult:
    request = Request(url, headers={"User-Agent": "InsiderSellerOfficialRagIngest/1.0", "Accept": "text/html,text/plain;q=0.9"})
    with urlopen(request, timeout=timeout) as response:  # nosec: URL is allowlist-checked before call.
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type not in TEXT_CONTENT_TYPES:
            raise ValueError(f"unsupported_content_type:{content_type or '<empty>'}")
        body = response.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ValueError(f"max_size_exceeded:{len(body)}>{max_bytes}")
    return FetchResult(url=url, content_type=content_type, body=body)


class _TextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "header", "footer", "form"}
    BLOCK_TAGS = {"p", "div", "section", "article", "main", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK_TAGS and self._skip_depth == 0:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag in self.BLOCK_TAGS and self._skip_depth == 0:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._skip_depth == 0 and not self._in_title:
            self.text_parts.append(data)


def compact_text(value: str) -> str:
    lines = []
    for line in html.unescape(value).replace("\r", "\n").split("\n"):
        cleaned = re.sub(r"[ \t\f\v]+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def extract_title_and_text(body: bytes, content_type: str) -> tuple[str, str]:
    text = body.decode("utf-8", errors="replace")
    if content_type == "text/plain":
        clean_text = compact_text(text)
        title = clean_text.split("\n", 1)[0][:200] if clean_text else ""
        return title, clean_text
    parser = _TextExtractor()
    parser.feed(text)
    parser.close()
    title = compact_text(" ".join(parser.title_parts))[:300]
    clean_text = compact_text(" ".join(parser.text_parts))
    if not title and clean_text:
        title = clean_text.split("\n", 1)[0][:200]
    return title, clean_text


def content_hash(clean_text: str) -> str:
    return hashlib.sha256(clean_text.encode("utf-8")).hexdigest()


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({q(table)})")]


def find_duplicate(conn: sqlite3.Connection, source_url: str, hash_value: str) -> str | None:
    if not table_exists(conn, "rag_documents"):
        raise RuntimeError("rag_documents table is missing")
    cols = set(table_columns(conn, "rag_documents"))
    if "content_hash" in cols:
        row = conn.execute("SELECT id FROM rag_documents WHERE content_hash=? LIMIT 1", (hash_value,)).fetchone()
        if row:
            return "duplicate_content_hash"
    if "source_url" in cols:
        row = conn.execute("SELECT id FROM rag_documents WHERE source_url=? LIMIT 1", (source_url,)).fetchone()
        if row:
            return "duplicate_source_url"
    if "external_id" in cols:
        row = conn.execute("SELECT id FROM rag_documents WHERE external_id=? LIMIT 1", (hash_value,)).fetchone()
        if row:
            return "duplicate_external_id_hash"
    return None


def ensure_source_id(conn: sqlite3.Connection, source: OfficialSource) -> int | None:
    if not table_exists(conn, "rag_sources"):
        return None
    cols = set(table_columns(conn, "rag_sources"))
    if not {"source_name", "source_url"}.issubset(cols):
        return None
    row = conn.execute("SELECT id FROM rag_sources WHERE source_url=? OR source_name=? LIMIT 1", (source.source_url, source.source_name)).fetchone()
    if row:
        return int(row[0])
    insert_cols = ["source_name", "source_url"]
    values: list[Any] = [source.source_name, source.source_url]
    if "status" in cols:
        insert_cols.append("status")
        values.append("active")
    placeholders = ", ".join("?" for _ in insert_cols)
    sql = f"INSERT INTO rag_sources ({', '.join(q(c) for c in insert_cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, values)
    return int(cur.lastrowid)


def insert_document(conn: sqlite3.Connection, source: OfficialSource, title: str, clean_text: str, hash_value: str) -> int:
    cols = set(table_columns(conn, "rag_documents"))
    values_by_col: dict[str, Any] = {
        "source_id": ensure_source_id(conn, source) if "source_id" in cols else None,
        "external_id": hash_value,
        "title": title,
        "body": clean_text,
        "clean_text": clean_text,
        "source_url": source.source_url,
        "url": source.source_url,
        "link": source.source_url,
        "source": source.source_name,
        "source_name": source.source_name,
        "source_key": source.source_key,
        "source_type": source.source_type,
        "rag_layer": source.rag_layer,
        "marketplace": source.marketplace,
        "trust_level": source.trust_level,
        "content_hash": hash_value,
        "rag_eligible": 1,
        "eligible": 1,
    }
    insert_cols = [col for col in values_by_col if col in cols and values_by_col[col] is not None]
    if not insert_cols:
        raise RuntimeError("rag_documents has no supported insert columns")
    sql = f"INSERT INTO rag_documents ({', '.join(q(c) for c in insert_cols)}) VALUES ({', '.join('?' for _ in insert_cols)})"
    cur = conn.execute(sql, [values_by_col[col] for col in insert_cols])
    return int(cur.lastrowid)


def process_source(
    conn: sqlite3.Connection,
    source: OfficialSource,
    dry_run: bool,
    fetcher: Callable[[str, int, int], FetchResult] = fetch_url,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "source_key": source.source_key,
        "url": source.source_url,
        "layer": source.rag_layer,
        "status": "pending",
        "title": "",
        "clean_text_len": 0,
        "content_hash": "",
        "result": "",
    }
    if not is_allowed_url(source.source_url):
        report.update(status="rejected", result="url_not_allowlisted")
        return report
    try:
        fetched = fetcher(source.source_url, timeout, max_bytes)
        title, clean_text = extract_title_and_text(fetched.body, fetched.content_type)
        hash_value = content_hash(clean_text)
        report.update(title=title, clean_text_len=len(clean_text), content_hash=hash_value)
        if not clean_text:
            report.update(status="skipped", result="empty_clean_text")
            return report
        duplicate_reason = find_duplicate(conn, source.source_url, hash_value)
        if duplicate_reason:
            report.update(status="skipped", result=duplicate_reason)
            return report
        if dry_run:
            report.update(status="dry_run", result="not_inserted")
            return report
        doc_id = insert_document(conn, source, title, clean_text, hash_value)
        conn.commit()
        report.update(status="inserted", result=f"document_id={doc_id}")
        return report
    except Exception as exc:  # concise operational report, not a stack trace
        report.update(status="error", result=str(exc))
        return report


def print_report(report: dict[str, Any]) -> None:
    print(
        " | ".join(
            [
                f"source_key={report.get('source_key', '')}",
                f"url={report.get('url', '')}",
                f"layer={report.get('layer', '')}",
                f"status={report.get('status', '')}",
                f"title={report.get('title', '')}",
                f"clean_text_len={report.get('clean_text_len', 0)}",
                f"content_hash={report.get('content_hash', '')}",
                f"result={report.get('result', '')}",
            ]
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest official/public RAG sources v1 (dry-run first)")
    parser.add_argument("--db", default=str(default_db()))
    parser.add_argument("--sources", default=str(SEED_PATH))
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report only; do not mutate rag_store.db")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--source-key", default=None)
    parser.add_argument("--layer", choices=RAG_LAYERS, default=None)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args(argv)

    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be non-negative")
    if args.max_bytes <= 0:
        parser.error("--max-bytes must be positive")

    sources = select_sources(load_sources(Path(args.sources)), args.source_key, args.layer, args.limit)
    db = Path(args.db)
    if not db.exists():
        print(f"ERROR: db_not_found={db}", file=sys.stderr)
        return 2
    conn = sqlite3.connect(db)
    try:
        if not table_exists(conn, "rag_documents"):
            print("ERROR: rag_documents table is missing", file=sys.stderr)
            return 2
        for source in sources:
            print_report(process_source(conn, source, dry_run=args.dry_run, timeout=args.timeout, max_bytes=args.max_bytes))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
