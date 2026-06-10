from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path
from urllib import error

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "ingest_official_rag_sources_v1.py"
spec = importlib.util.spec_from_file_location("official_rag_ingest", MODULE_PATH)
official_rag_ingest = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = official_rag_ingest
spec.loader.exec_module(official_rag_ingest)


class _Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _FakeResponse:
    def __init__(self, body: bytes, content_type: str = "text/html"):
        self.body = body
        self.headers = _Headers({"Content-Type": content_type})
        self.url = "https://example.test/final"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, n=-1):
        return self.body if n < 0 else self.body[:n]


def make_db(tmp_path: Path, source_rows: list[tuple[str, str]]) -> sqlite3.Connection:
    db_path = tmp_path / "rag_store.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE analytics_source_registry (
            source_key TEXT UNIQUE NOT NULL,
            source_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_url TEXT,
            marketplace TEXT,
            product_scope TEXT,
            rag_layer TEXT NOT NULL,
            trust_level TEXT NOT NULL,
            document_type TEXT
        );
        CREATE TABLE rag_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT,
            source_url TEXT,
            status TEXT
        );
        CREATE TABLE rag_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER,
            external_id TEXT,
            title TEXT,
            body TEXT,
            source_url TEXT,
            content_hash TEXT
        );
        """
    )
    conn.executemany(
        """
        INSERT INTO analytics_source_registry (
            source_key, source_name, source_type, source_url, marketplace,
            product_scope, rag_layer, trust_level, document_type
        ) VALUES (?, ?, 'official', ?, 'ozon', '', 'marketplace_offer', 'high', 'official_news')
        """,
        [(key, key, url) for key, url in source_rows],
    )
    conn.commit()
    return conn


def test_empty_clean_text_has_empty_hash_and_is_skipped(monkeypatch, tmp_path):
    conn = make_db(tmp_path, [("empty", "https://example.test/empty")])
    source = official_rag_ingest.load_sources(conn)[0]

    monkeypatch.setattr(
        official_rag_ingest,
        "fetch_url",
        lambda *args, **kwargs: official_rag_ingest.FetchResult("https://example.test/empty", "text/html", b"<html><script>x</script></html>"),
    )

    result = official_rag_ingest.process_source(conn, source, dry_run=True, timeout=1, max_bytes=1000)

    assert result["status"] == "skipped"
    assert result["result"] == "empty_clean_text"
    assert result["content_hash"] == ""
    assert result["clean_text_len"] == 0


def test_no_insertion_for_empty_clean_text(monkeypatch, tmp_path):
    conn = make_db(tmp_path, [("empty", "https://example.test/empty")])
    source = official_rag_ingest.load_sources(conn)[0]
    monkeypatch.setattr(
        official_rag_ingest,
        "fetch_url",
        lambda *args, **kwargs: official_rag_ingest.FetchResult("https://example.test/empty", "text/plain", b"   \n\t  "),
    )

    result = official_rag_ingest.process_source(conn, source, dry_run=False, timeout=1, max_bytes=1000)

    assert result["status"] == "skipped"
    assert result["content_hash"] == ""
    assert conn.execute("SELECT COUNT(*) FROM rag_documents").fetchone()[0] == 0


def test_timeout_is_classified_as_timeout():
    exc = error.URLError(TimeoutError("timed out"))
    assert official_rag_ingest.classify_fetch_exception(exc) == "timeout"


def test_redirect_loop_http_307_is_classified_as_redirect_loop():
    exc = error.HTTPError("https://example.test", 307, "Temporary Redirect", hdrs=None, fp=None)
    assert official_rag_ingest.classify_fetch_exception(exc) == "redirect_loop"


def test_unsupported_content_type_is_expected_fetch_error(monkeypatch):
    monkeypatch.setattr(
        official_rag_ingest.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(b"%PDF", "application/pdf"),
    )

    try:
        official_rag_ingest.fetch_url("https://example.test/file.pdf", timeout=1, max_bytes=1000)
    except official_rag_ingest.FetchError as exc:
        assert exc.error_type == "unsupported_content_type"
        assert "unsupported content type" in str(exc)
    else:
        raise AssertionError("unsupported content type must raise FetchError")


def test_batch_processing_continues_after_one_failing_source(monkeypatch, tmp_path, capsys):
    conn = make_db(
        tmp_path,
        [
            ("bad", "https://example.test/bad"),
            ("good", "https://example.test/good"),
        ],
    )

    def fake_fetch(url, *, timeout, max_bytes):
        if url.endswith("/bad"):
            raise official_rag_ingest.FetchError("timed out", "timeout")
        return official_rag_ingest.FetchResult(url, "text/html", b"<html><title>Good</title><p>Useful official text.</p></html>")

    monkeypatch.setattr(official_rag_ingest, "fetch_url", fake_fetch)

    for source in official_rag_ingest.load_sources(conn, limit=2):
        print(official_rag_ingest.format_result(official_rag_ingest.process_source(conn, source, dry_run=True, timeout=1, max_bytes=1000)))

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2
    assert "source_key=bad" in lines[0]
    assert "status=error" in lines[0]
    assert "error_type=timeout" in lines[0]
    assert "source_key=good" in lines[1]
    assert "status=dry_run" in lines[1]
    assert "error_type=" in lines[1]
