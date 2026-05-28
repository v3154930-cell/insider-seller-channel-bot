import sqlite3

from app.db import get_v3_db_path
from tools import v3_controlled_send_canary as canary


def _make_v2_db(path: str) -> None:
    con = sqlite3.connect(path)
    con.execute(
        """
        CREATE TABLE news(
            id INTEGER PRIMARY KEY,
            title TEXT,
            text TEXT,
            link TEXT,
            source TEXT,
            created_at TEXT,
            seller_decision TEXT,
            seller_relevance_score INTEGER,
            actionability_score INTEGER,
            is_published INTEGER,
            max_message_id TEXT
        )
        """
    )
    con.execute(
        "INSERT INTO news VALUES(90045, 'WB тариф для продавцов', 'body', 'https://example.com/1', 'TG:mpgo_ru', '2026-05-27T10:00:00', 'publish', 6, 6, 0, '')"
    )
    con.commit()
    con.close()


def _row_count(path: str, table: str) -> int:
    con = sqlite3.connect(path)
    count = con.execute(f"SELECT COUNT(1) FROM {table}").fetchone()[0]
    con.close()
    return int(count)


def _v2_publish_state(path: str, news_id: int) -> tuple[int, str]:
    con = sqlite3.connect(path)
    row = con.execute("SELECT is_published, COALESCE(max_message_id, '') FROM news WHERE id = ?", (news_id,)).fetchone()
    con.close()
    return int(row[0]), str(row[1] or "")


def test_dry_run_unchanged(monkeypatch, tmp_path, capsys):
    v2_db = tmp_path / "v2.db"
    v3_db = tmp_path / "v3.db"
    _make_v2_db(str(v2_db))
    monkeypatch.setenv("V3_DB", str(v3_db))
    monkeypatch.setattr("sys.argv", ["v3_controlled_send_canary.py", "--v2-db", str(v2_db), "--v2-id", "90045"])

    rc = canary.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "V3_CONTROLLED_SEND_STATUS=DRY_RUN" in out
    assert "send_status=dry_run" in out
    assert "raw_source_url_in_main_post=false" in out
    assert "source_link_preview_suppressed=true" in out
    assert "source_url_button_used=false" in out
    assert "external_url_button_forbidden=true" in out


def test_mock_mode_allows_mock_message_id(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWSBOT_V3_REAL_SEND", "false")
    monkeypatch.setenv("NEWSBOT_V3_MOCK_MAX", "true")
    client = canary.MaxClient.from_env(target_channel="mock-channel")

    resp = client.send_text("mock-channel", "hello")

    assert str(resp.get("message_id", "")).startswith("mock-msg-")


def test_real_send_with_mock_msg_fails_closed_and_no_runtime_writes(monkeypatch, tmp_path, capsys):
    v2_db = tmp_path / "v2.db"
    v3_db = tmp_path / "v3.db"
    _make_v2_db(str(v2_db))

    monkeypatch.setenv("V3_DB", str(v3_db))
    monkeypatch.setenv("NEWSBOT_V3_REAL_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_CUTOVER_CONFIRM", canary.REQUIRED_CONFIRM)
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_TEST_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_MAX_TOKEN", "token")
    monkeypatch.setenv("NEWSBOT_V3_MOCK_MAX", "false")

    monkeypatch.setattr("sys.argv", ["v3_controlled_send_canary.py", "--execute", "--v2-db", str(v2_db), "--v2-id", "90045"])
    monkeypatch.setattr(
        "app.max_client.requests.post",
        lambda *args, **kwargs: type("R", (), {"status_code": 200, "json": lambda self: {"message": {"body": {"mid": "mock-msg-fake"}}}, "text": ""})(),
    )

    rc = canary.main()
    out = capsys.readouterr().out

    assert rc == 1
    assert "V3_CONTROLLED_SEND_STATUS=FAIL" in out
    assert "send_status=failed_mock_message_id_for_real_send" in out
    assert "mock_message_id_forbidden=true" in out
    assert "max_guard_ok=true" in out

    v3_path = str(get_v3_db_path())
    assert _row_count(v3_path, "send_attempts") == 0
    assert _row_count(v3_path, "published_messages") == 0
    assert _row_count(v3_path, "system_events") == 0


def test_real_send_success_records_runtime_rows(monkeypatch, tmp_path, capsys):
    v2_db = tmp_path / "v2.db"
    v3_db = tmp_path / "v3.db"
    _make_v2_db(str(v2_db))
    monkeypatch.setenv("V3_DB", str(v3_db))
    monkeypatch.setenv("NEWSBOT_V3_REAL_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_CUTOVER_CONFIRM", canary.REQUIRED_CONFIRM)
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_TEST_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_MAX_TOKEN", "token")
    monkeypatch.setenv("NEWSBOT_V3_MOCK_MAX", "false")
    monkeypatch.setattr(
        "app.max_client.requests.post",
        lambda *args, **kwargs: type("R", (), {"status_code": 200, "json": lambda self: {"message": {"body": {"mid": "real-mid-1"}}}, "text": ""})(),
    )
    monkeypatch.setattr("sys.argv", ["v3_controlled_send_canary.py", "--execute", "--v2-db", str(v2_db), "--v2-id", "90045"])
    rc = canary.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "V3_CONTROLLED_SEND_STATUS=OK" in out
    assert "send_status=sent" in out
    assert "max_message_id=real-mid-1" in out
    v3_path = str(get_v3_db_path())
    assert _row_count(v3_path, "send_attempts") == 1
    assert _row_count(v3_path, "published_messages") == 1


def test_real_send_http_failure_has_no_runtime_writes(monkeypatch, tmp_path, capsys):
    v2_db = tmp_path / "v2.db"
    v3_db = tmp_path / "v3.db"
    _make_v2_db(str(v2_db))
    monkeypatch.setenv("V3_DB", str(v3_db))
    monkeypatch.setenv("NEWSBOT_V3_REAL_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_CUTOVER_CONFIRM", canary.REQUIRED_CONFIRM)
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_TEST_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_MAX_TOKEN", "token")
    monkeypatch.setenv("NEWSBOT_V3_MOCK_MAX", "false")
    monkeypatch.setattr(
        "app.max_client.requests.post",
        lambda *args, **kwargs: type("R", (), {"status_code": 500, "json": lambda self: {}, "text": "boom"})(),
    )
    monkeypatch.setattr("sys.argv", ["v3_controlled_send_canary.py", "--execute", "--v2-db", str(v2_db), "--v2-id", "90045"])
    rc = canary.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "send_status=failed_main_send" in out
    v3_path = str(get_v3_db_path())
    assert _row_count(v3_path, "send_attempts") == 0
    assert _row_count(v3_path, "published_messages") == 0


def test_skip_if_v2_already_published_before_send(monkeypatch, tmp_path, capsys):
    v2_db = tmp_path / "v2.db"
    v3_db = tmp_path / "v3.db"
    _make_v2_db(str(v2_db))
    monkeypatch.setenv("V3_DB", str(v3_db))
    monkeypatch.setenv("NEWSBOT_V3_REAL_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_CUTOVER_CONFIRM", canary.REQUIRED_CONFIRM)
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_TEST_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_MAX_TOKEN", "token")
    monkeypatch.setenv("NEWSBOT_V3_MOCK_MAX", "false")
    monkeypatch.setattr(canary, "_fetch_v2_publish_state", lambda *args, **kwargs: (1, "mid.v2.already"))
    monkeypatch.setattr("sys.argv", ["v3_controlled_send_canary.py", "--execute", "--v2-db", str(v2_db), "--v2-id", "90045"])

    rc = canary.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "V3_CONTROLLED_SEND_STATUS=SKIPPED" in out
    assert "send_status=skipped_v2_already_published" in out
    assert "v2_pre_send_is_published=1" in out
    assert "v2_pre_send_max_message_id=mid.v2.already" in out

    assert not v3_db.exists()


def test_mark_v2_published_after_success_when_enabled(monkeypatch, tmp_path, capsys):
    v2_db = tmp_path / "v2.db"
    v3_db = tmp_path / "v3.db"
    _make_v2_db(str(v2_db))
    monkeypatch.setenv("V3_DB", str(v3_db))
    monkeypatch.setenv("NEWSBOT_V3_REAL_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_CUTOVER_CONFIRM", canary.REQUIRED_CONFIRM)
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_TEST_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_MAX_TOKEN", "token")
    monkeypatch.setenv("NEWSBOT_V3_MOCK_MAX", "false")
    monkeypatch.setenv("NEWSBOT_V3_MARK_V2_PUBLISHED", "true")
    monkeypatch.setattr(
        "app.max_client.requests.post",
        lambda *args, **kwargs: type("R", (), {"status_code": 200, "json": lambda self: {"message": {"body": {"mid": "real-mid-2"}}}, "text": ""})(),
    )
    monkeypatch.setattr("sys.argv", ["v3_controlled_send_canary.py", "--execute", "--v2-db", str(v2_db), "--v2-id", "90045"])
    rc = canary.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "send_status=sent" in out
    assert "v2_mark_published_enabled=true" in out
    assert "v2_marked_published_by_v3=true" in out

    is_pub, max_mid = _v2_publish_state(str(v2_db), 90045)
    assert is_pub == 1
    assert max_mid == "real-mid-2"


def test_without_mark_flag_v2_remains_unchanged(monkeypatch, tmp_path, capsys):
    v2_db = tmp_path / "v2.db"
    v3_db = tmp_path / "v3.db"
    _make_v2_db(str(v2_db))
    monkeypatch.setenv("V3_DB", str(v3_db))
    monkeypatch.setenv("NEWSBOT_V3_REAL_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_CUTOVER_CONFIRM", canary.REQUIRED_CONFIRM)
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_TEST_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_MAX_TOKEN", "token")
    monkeypatch.setenv("NEWSBOT_V3_MOCK_MAX", "false")
    monkeypatch.delenv("NEWSBOT_V3_MARK_V2_PUBLISHED", raising=False)
    monkeypatch.setattr(
        "app.max_client.requests.post",
        lambda *args, **kwargs: type("R", (), {"status_code": 200, "json": lambda self: {"message": {"body": {"mid": "real-mid-3"}}}, "text": ""})(),
    )
    monkeypatch.setattr("sys.argv", ["v3_controlled_send_canary.py", "--execute", "--v2-db", str(v2_db), "--v2-id", "90045"])
    rc = canary.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "send_status=sent" in out
    assert "v2_mark_published_enabled=false" in out
    assert "v2_marked_published_by_v3=false" in out

    is_pub, max_mid = _v2_publish_state(str(v2_db), 90045)
    assert is_pub == 0
    assert max_mid == ""
