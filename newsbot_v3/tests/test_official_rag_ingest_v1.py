from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools import ingest_official_rag_sources_v1 as ingest


def source() -> ingest.OfficialSource:
    return ingest.OfficialSource(
        source_key="wildberries_seller_news_official",
        source_name="Wildberries",
        source_url="https://example.test/wb",
    )


@pytest.fixture
def fail_hash(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("quality gates must run before sha256")

    monkeypatch.setattr(hashlib, "sha256", boom)


def test_clean_text_len_below_threshold_is_skipped_before_hash(fail_hash):
    result = ingest.process_extracted_document(
        source(),
        title="Useful official page",
        clean_text="short official text",
        min_clean_text_chars=300,
        dry_run=True,
    )

    assert result["status"] == "skipped"
    assert result["error_type"] == "too_short_clean_text"
    assert result["result"] == "too_short_clean_text"
    assert result["clean_text_len"] == len("short official text")


def test_content_hash_is_empty_for_too_short_clean_text(fail_hash):
    result = ingest.process_extracted_document(
        source(),
        title="Wildberries",
        clean_text="placeholder",
        min_clean_text_chars=500,
        dry_run=True,
    )

    assert result["error_type"] == "too_short_clean_text"
    assert result["content_hash"] == ""
    assert result["generic_title"] is True


def test_mojibake_title_is_skipped_before_hash(fail_hash):
    result = ingest.process_extracted_document(
        source(),
        title="���������������",
        clean_text="Официальный текст " * 80,
        min_clean_text_chars=300,
        dry_run=True,
    )

    assert result["status"] == "skipped"
    assert result["error_type"] == "mojibake_detected"
    assert result["content_hash"] == ""
    assert result["result"] == "mojibake_detected"


def test_mojibake_clean_text_is_skipped_before_hash(fail_hash):
    clean_text = ("Официальный текст для проверки. " * 30) + "��������"
    result = ingest.process_extracted_document(
        source(),
        title="Official regulation project portal",
        clean_text=clean_text,
        min_clean_text_chars=300,
        dry_run=True,
    )

    assert result["status"] == "skipped"
    assert result["error_type"] == "mojibake_detected"
    assert result["content_hash"] == ""


def test_valid_official_text_above_threshold_still_would_insert_in_dry_run():
    result = ingest.process_extracted_document(
        source(),
        title="Official marketplace seller rules update",
        clean_text="This official seller rules update describes tariff, logistics, and compliance changes. " * 10,
        min_clean_text_chars=300,
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["error_type"] == ""
    assert result["result"] == "would_insert"
    assert result["content_hash"]
    assert len(result["content_hash"]) == 64


def test_cli_accepts_min_clean_text_chars(tmp_path):
    db = tmp_path / "rag_store.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE analytics_source_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT,
            source_name TEXT,
            source_type TEXT,
            source_url TEXT,
            marketplace TEXT,
            rag_layer TEXT,
            trust_level TEXT,
            document_type TEXT,
            ingest_status TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    script = Path(__file__).resolve().parents[1] / "tools" / "ingest_official_rag_sources_v1.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--db",
            str(db),
            "--dry-run",
            "--min-clean-text-chars",
            "300",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout == ""
