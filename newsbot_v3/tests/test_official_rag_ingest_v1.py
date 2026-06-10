import sqlite3

from tools import ingest_official_rag_sources_v1 as ingest


def make_db(tmp_path):
    db = tmp_path / "rag_store.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE rag_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT,
            source_name TEXT,
            source_type TEXT,
            source_url TEXT,
            marketplace TEXT,
            rag_layer TEXT,
            trust_level TEXT,
            title TEXT,
            clean_text TEXT,
            body TEXT,
            content_hash TEXT,
            rag_eligible INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def source(url="https://pravo.gov.ru/", layer="legal_official", marketplace="all", key="test_source"):
    return ingest.OfficialSource(
        source_key=key,
        source_name="Test Official Source",
        source_url=url,
        source_type="official_html",
        rag_layer=layer,
        marketplace=marketplace,
        trust_level="high",
        refresh_policy="manual_dry_run_first",
        notes="fixture",
    )


def fetcher_with(body, content_type="text/html"):
    def _fetcher(url, timeout, max_bytes):
        raw = body.encode("utf-8")
        if len(raw) > max_bytes:
            raise ValueError(f"max_size_exceeded:{len(raw)}>{max_bytes}")
        return ingest.FetchResult(url=url, content_type=content_type, body=raw)

    return _fetcher


def test_allowed_official_url_is_accepted():
    assert ingest.is_allowed_url("https://pravo.gov.ru/some/path")
    assert ingest.is_allowed_url("https://www.nalog.gov.ru/rn77/")


def test_non_allowlisted_url_is_rejected(tmp_path):
    conn = make_db(tmp_path)
    report = ingest.process_source(
        conn,
        source(url="https://example.com/legal"),
        dry_run=True,
        fetcher=fetcher_with("<html><title>Bad</title><p>Text</p></html>"),
    )
    assert report["status"] == "rejected"
    assert report["result"] == "url_not_allowlisted"
    assert conn.execute("SELECT COUNT(*) FROM rag_documents").fetchone()[0] == 0


def test_dry_run_does_not_insert(tmp_path):
    conn = make_db(tmp_path)
    report = ingest.process_source(
        conn,
        source(),
        dry_run=True,
        fetcher=fetcher_with("<html><title>Official title</title><main><p>Useful legal text.</p></main></html>"),
    )
    assert report["status"] == "dry_run"
    assert report["result"] == "not_inserted"
    assert conn.execute("SELECT COUNT(*) FROM rag_documents").fetchone()[0] == 0


def test_duplicate_content_hash_is_skipped(tmp_path):
    conn = make_db(tmp_path)
    html = "<html><title>Official title</title><main><p>Same official text.</p></main></html>"
    first = ingest.process_source(conn, source(), dry_run=False, fetcher=fetcher_with(html))
    second = ingest.process_source(conn, source(key="test_source_2", url="https://pravo.gov.ru/another"), dry_run=False, fetcher=fetcher_with(html))
    assert first["status"] == "inserted"
    assert second["status"] == "skipped"
    assert second["result"] == "duplicate_content_hash"
    assert conn.execute("SELECT COUNT(*) FROM rag_documents").fetchone()[0] == 1


def test_marketplace_offer_source_is_tagged_correctly(tmp_path):
    conn = make_db(tmp_path)
    report = ingest.process_source(
        conn,
        source(url="https://seller.ozon.ru/media/news/", layer="marketplace_offer", marketplace="ozon"),
        dry_run=False,
        fetcher=fetcher_with("<html><title>Ozon rules</title><main><p>Seller offer update.</p></main></html>"),
    )
    row = conn.execute("SELECT rag_layer, marketplace FROM rag_documents").fetchone()
    assert report["status"] == "inserted"
    assert row == ("marketplace_offer", "ozon")


def test_legal_official_source_is_tagged_correctly(tmp_path):
    conn = make_db(tmp_path)
    report = ingest.process_source(
        conn,
        source(layer="legal_official"),
        dry_run=False,
        fetcher=fetcher_with("<html><title>Law</title><main><p>Official law text.</p></main></html>"),
    )
    row = conn.execute("SELECT rag_layer, trust_level FROM rag_documents").fetchone()
    assert report["status"] == "inserted"
    assert row == ("legal_official", "high")


def test_max_size_limit_is_enforced(tmp_path):
    conn = make_db(tmp_path)
    report = ingest.process_source(
        conn,
        source(),
        dry_run=False,
        max_bytes=10,
        fetcher=fetcher_with("x" * 20, content_type="text/plain"),
    )
    assert report["status"] == "error"
    assert report["result"].startswith("max_size_exceeded")
    assert conn.execute("SELECT COUNT(*) FROM rag_documents").fetchone()[0] == 0


def test_clean_text_extraction_removes_script_style_nav_like_noise():
    title, clean_text = ingest.extract_title_and_text(
        b"""
        <html>
          <head><title> Page title </title><style>.x{display:none}</style><script>alert('x')</script></head>
          <body>
            <header>Header noise</header>
            <nav>Menu noise</nav>
            <main><h1>Important heading</h1><p>Useful paragraph for sellers.</p></main>
            <footer>Footer noise</footer>
          </body>
        </html>
        """,
        "text/html",
    )
    assert title == "Page title"
    assert "Important heading" in clean_text
    assert "Useful paragraph for sellers." in clean_text
    assert "alert" not in clean_text
    assert "Menu noise" not in clean_text
    assert "Header noise" not in clean_text
    assert "Footer noise" not in clean_text


def test_registry_seed_has_legacy_compatible_fallback_for_new_layers_and_types():
    from tools import init_analytics_source_registry_v1 as registry

    row = (
        "ozon_offer",
        "Ozon offer",
        "official_html",
        "https://seller.ozon.ru/media/news/",
        "ozon",
        "official/public RAG source",
        "marketplace_offer",
        "high",
        "marketplace_offer",
        "planned",
        "manual_dry_run_first",
        "fixture",
    )
    fallback = registry.with_legacy_registry_fallback(row)

    assert fallback is not None
    assert fallback[2] == "official"
    assert fallback[6] == "official_signal"
    assert "requested_source_type=official_html" in fallback[11]
    assert "requested_rag_layer=marketplace_offer" in fallback[11]
