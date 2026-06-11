import importlib.util
import sqlite3
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "ingest_official_rag_sources_v1.py"
spec = importlib.util.spec_from_file_location("official_rag_ingest", MODULE_PATH)
official_rag_ingest = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = official_rag_ingest
spec.loader.exec_module(official_rag_ingest)


def make_db(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE analytics_source_registry (
            source_key TEXT UNIQUE NOT NULL,
            source_name TEXT,
            source_type TEXT,
            source_url TEXT,
            marketplace TEXT,
            rag_layer TEXT,
            trust_level TEXT,
            document_type TEXT
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO analytics_source_registry (
            source_key, source_name, source_type, source_url, marketplace,
            rag_layer, trust_level, document_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("nalog_tax_official", "FNS tax official", "official", "https://example.test/nalog", "multiple", "legal_official", "high", "tax"),
            ("wb_tariff_official", "WB tariffs", "official", "https://example.test/wb", "wildberries", "tariff_official", "high", "tariff"),
            ("legal_docs_official", "Legal docs", "official", "https://example.test/legal", "multiple", "legal_official", "high", "legal"),
        ],
    )
    conn.commit()
    return conn


def rows(conn):
    return [dict(row) for row in conn.execute("SELECT * FROM rag_documents ORDER BY id")]


def successful_fetch(url, timeout_seconds):
    return official_rag_ingest.FetchResult(
        status="ok",
        final_url=url,
        content_type="text/html; charset=utf-8",
        body=("<html><body>" + ("Официальный текст для продавцов. " * 20) + "</body></html>").encode("utf-8"),
    )


def test_cli_accepts_source_key():
    args = official_rag_ingest.parse_args(["--source-key", "nalog_tax_official", "--dry-run"])
    assert args.source_key == "nalog_tax_official"
    assert args.dry_run is True


def test_source_key_filter_processes_only_requested_source(tmp_path, monkeypatch):
    db = tmp_path / "rag.db"
    conn = make_db(db)
    conn.close()
    called = []

    def fake_fetch(url, timeout_seconds):
        called.append(url)
        return successful_fetch(url, timeout_seconds)

    monkeypatch.setattr(official_rag_ingest, "fetch_url", fake_fetch)

    rc = official_rag_ingest.main(["--db", str(db), "--source-key", "nalog_tax_official", "--min-clean-text-chars", "10"])

    assert rc == 0
    assert called == ["https://example.test/nalog"]
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    docs = rows(conn)
    assert [doc["source_key"] for doc in docs] == ["nalog_tax_official"]
    assert docs[0]["content_hash"]


def test_unknown_source_key_exits_nonzero_with_clear_error(tmp_path, capsys):
    db = tmp_path / "rag.db"
    conn = make_db(db)
    conn.close()

    rc = official_rag_ingest.main(["--db", str(db), "--source-key", "missing_source"])

    captured = capsys.readouterr()
    assert rc != 0
    assert "source_key not found" in captured.err
    assert "missing_source" in captured.err


def test_cli_accepts_layer():
    args = official_rag_ingest.parse_args(["--layer", "legal_official", "--dry-run"])
    assert args.layer == "legal_official"
    assert args.dry_run is True


def test_layer_filter_processes_only_matching_sources(tmp_path, monkeypatch):
    db = tmp_path / "rag.db"
    conn = make_db(db)
    conn.close()
    called = []

    def fake_fetch(url, timeout_seconds):
        called.append(url)
        return successful_fetch(url, timeout_seconds)

    monkeypatch.setattr(official_rag_ingest, "fetch_url", fake_fetch)

    rc = official_rag_ingest.main(["--db", str(db), "--layer", "legal_official", "--min-clean-text-chars", "10"])

    assert rc == 0
    assert called == ["https://example.test/legal", "https://example.test/nalog"]
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    docs = rows(conn)
    assert [doc["source_key"] for doc in docs] == ["legal_docs_official", "nalog_tax_official"]
    assert {doc["rag_layer"] for doc in docs} == {"legal_official"}


def test_too_short_clean_text_gate_leaves_empty_content_hash(tmp_path, monkeypatch):
    db = tmp_path / "rag.db"
    conn = make_db(db)
    conn.close()

    monkeypatch.setattr(
        official_rag_ingest,
        "fetch_url",
        lambda url, timeout_seconds: official_rag_ingest.FetchResult("ok", url, "text/html", b"<p>short</p>"),
    )

    rc = official_rag_ingest.main(["--db", str(db), "--source-key", "nalog_tax_official", "--min-clean-text-chars", "50"])

    assert rc == 0
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    doc = rows(conn)[0]
    assert doc["ingest_status"] == "skipped"
    assert doc["skip_reason"] == "too_short_clean_text"
    assert doc["content_hash"] == ""


def test_mojibake_gate_leaves_empty_content_hash(tmp_path, monkeypatch):
    db = tmp_path / "rag.db"
    conn = make_db(db)
    conn.close()
    bad_text = "РџСЂРѕРґР°РІС†С‹ " * 20

    monkeypatch.setattr(
        official_rag_ingest,
        "fetch_url",
        lambda url, timeout_seconds: official_rag_ingest.FetchResult("ok", url, "text/plain", bad_text.encode("utf-8")),
    )

    rc = official_rag_ingest.main(["--db", str(db), "--source-key", "nalog_tax_official", "--min-clean-text-chars", "10"])

    assert rc == 0
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    doc = rows(conn)[0]
    assert doc["ingest_status"] == "skipped"
    assert doc["skip_reason"] == "mojibake_detected"
    assert doc["content_hash"] == ""


def test_unsupported_content_type_gate_leaves_empty_content_hash(tmp_path, monkeypatch):
    db = tmp_path / "rag.db"
    conn = make_db(db)
    conn.close()

    monkeypatch.setattr(
        official_rag_ingest,
        "fetch_url",
        lambda url, timeout_seconds: official_rag_ingest.FetchResult("ok", url, "image/png", b"not text"),
    )

    rc = official_rag_ingest.main(["--db", str(db), "--source-key", "nalog_tax_official"])

    assert rc == 0
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    doc = rows(conn)[0]
    assert doc["ingest_status"] == "skipped"
    assert doc["skip_reason"] == "unsupported_content_type"
    assert doc["content_hash"] == ""


def test_duplicate_source_url_gate_leaves_empty_content_hash(tmp_path, monkeypatch):
    db = tmp_path / "rag.db"
    conn = make_db(db)
    official_rag_ingest.ensure_rag_documents(conn)
    conn.execute(
        "INSERT INTO rag_documents (source_key, source_url, ingest_status, content_hash) VALUES (?, ?, ?, ?)",
        ("old", "https://example.test/nalog", "ingested", "abc"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(official_rag_ingest, "fetch_url", lambda url, timeout_seconds: (_ for _ in ()).throw(AssertionError("must not fetch duplicate")))

    rc = official_rag_ingest.main(["--db", str(db), "--source-key", "nalog_tax_official"])

    assert rc == 0
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    docs = rows(conn)
    assert docs[-1]["ingest_status"] == "skipped"
    assert docs[-1]["skip_reason"] == "duplicate_source_url"
    assert docs[-1]["content_hash"] == ""


def test_timeout_and_http_error_gates_leave_empty_content_hash(tmp_path, monkeypatch):
    db = tmp_path / "rag.db"
    conn = make_db(db)
    conn.close()

    def timeout_fetch(url, timeout_seconds):
        raise TimeoutError("timed out")

    monkeypatch.setattr(official_rag_ingest, "fetch_url", timeout_fetch)
    rc = official_rag_ingest.main(["--db", str(db), "--source-key", "nalog_tax_official"])
    assert rc == 0

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    doc = rows(conn)[0]
    assert doc["ingest_status"] == "error"
    assert doc["error_reason"] == "timeout"
    assert doc["content_hash"] == ""


def test_http_error_gate_leaves_empty_content_hash(tmp_path, monkeypatch):
    from urllib import error

    db = tmp_path / "rag.db"
    conn = make_db(db)
    conn.close()

    def http_error_fetch(url, timeout_seconds):
        raise error.HTTPError(url, 500, "server error", {}, None)

    monkeypatch.setattr(official_rag_ingest, "fetch_url", http_error_fetch)
    rc = official_rag_ingest.main(["--db", str(db), "--source-key", "nalog_tax_official"])

    assert rc == 0
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    doc = rows(conn)[0]
    assert doc["ingest_status"] == "error"
    assert doc["error_reason"] == "http_error"
    assert doc["content_hash"] == ""


def test_redirect_loop_gate_leaves_empty_content_hash(tmp_path, monkeypatch):
    db = tmp_path / "rag.db"
    conn = make_db(db)
    conn.close()

    def redirect_fetch(url, timeout_seconds):
        raise RuntimeError("redirect loop detected")

    monkeypatch.setattr(official_rag_ingest, "fetch_url", redirect_fetch)
    rc = official_rag_ingest.main(["--db", str(db), "--source-key", "nalog_tax_official"])

    assert rc == 0
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    doc = rows(conn)[0]
    assert doc["ingest_status"] == "error"
    assert doc["error_reason"] == "redirect_loop"
    assert doc["content_hash"] == ""
