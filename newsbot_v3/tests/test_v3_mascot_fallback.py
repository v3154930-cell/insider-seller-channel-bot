import sqlite3

from tools import v3_controlled_send_canary as canary


def _env(monkeypatch, v3_db):
    monkeypatch.setenv("V3_DB", str(v3_db))
    monkeypatch.setenv("NEWSBOT_V3_REAL_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_SEND", "true")
    monkeypatch.setenv("NEWSBOT_V3_CUTOVER_CONFIRM", canary.REQUIRED_CONFIRM)
    monkeypatch.setenv("NEWSBOT_V3_PRODUCTION_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_TEST_CHANNEL_ID", "ch-test")
    monkeypatch.setenv("NEWSBOT_V3_MAX_TOKEN", "token")
    monkeypatch.setenv("NEWSBOT_V3_MOCK_MAX", "false")
    monkeypatch.setenv("NEWSBOT_V3_MARK_V2_PUBLISHED", "true")
    monkeypatch.setenv("NEWSBOT_V3_SEND_MASCOT_ATTACHMENTS", "true")


def _make_long_db(path):
    con = sqlite3.connect(path)
    con.execute(
        """
        CREATE TABLE news(
            id INTEGER PRIMARY KEY,
            title TEXT,
            full_text TEXT,
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
        "INSERT INTO news VALUES(123, ?, ?, ?, ?, ?, 'publish', 6, 6, 0, '')",
        (
            "WB тариф для продавцов",
            "селлер wildberries " + ("подробности " * 260),
            "https://e.test/123",
            "src",
            "2026-05-29T10:00:00",
        ),
    )
    con.commit()
    con.close()


def _state(path):
    con = sqlite3.connect(path)
    row = con.execute("SELECT seller_decision, COALESCE(is_published,0), COALESCE(max_message_id,'') FROM news WHERE id=123").fetchone()
    con.close()
    return row


class ImageFailsTextSucceedsClient:
    @classmethod
    def from_env(cls, target_channel=""):
        return cls()

    def diagnostics(self):
        return {"max_mode": "limited_live", "max_guard_ok": True}

    def send_text_with_callback_button_and_image(self, *args, **kwargs):
        raise canary.MaxClientSendError("image upload HTTP 500")

    def send_text_with_callback_button(self, *args, **kwargs):
        return {"ok": True, "message_id": "mid-fallback"}

    def send_text_with_url_button(self, *args, **kwargs):
        return {"ok": True, "message_id": "mid-cta"}

    def extract_message_id(self, response):
        return response.get("message_id")

    def validate_visible_delivery(self, response):
        return bool(response.get("message_id"))


class ImageAndTextFailClient(ImageFailsTextSucceedsClient):
    def send_text_with_callback_button(self, *args, **kwargs):
        raise canary.MaxClientSendError("text send HTTP 502")


def test_image_send_failure_falls_back_to_text_send(monkeypatch, tmp_path, capsys):
    v2_db = tmp_path / "v2.db"
    v3_db = tmp_path / "v3.db"
    mascot = tmp_path / "mascot.png"
    mascot.write_bytes(b"fake")
    _make_long_db(v2_db)
    _env(monkeypatch, v3_db)
    monkeypatch.setattr(canary, "visuals_enabled", lambda: True)
    monkeypatch.setattr(canary, "select_mascot_asset", lambda **kwargs: ("base_friendly", str(mascot)))
    monkeypatch.setattr(canary, "MaxClient", ImageFailsTextSucceedsClient)
    monkeypatch.setattr("sys.argv", ["v3_controlled_send_canary.py", "--execute", "--v2-db", str(v2_db), "--v2-id", "123"])

    rc = canary.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "send_status=sent" in out
    assert "max_send_method=send_text_with_callback_button_fallback_after_image_failed" in out
    assert "mascot_attachment_sent=false" in out
    assert "mascot_send_status=fallback_text_after_image_failed" in out
    assert "primary_send_error=image upload HTTP 500" in out
    assert "v2_marked_published_by_v3=true" in out
    assert "v2_send_failed_quarantined=true" not in out
    assert _state(v2_db) == ("publish", 1, "mid-fallback")


def test_image_send_failure_and_text_failure_quarantines_candidate(monkeypatch, tmp_path, capsys):
    v2_db = tmp_path / "v2.db"
    v3_db = tmp_path / "v3.db"
    mascot = tmp_path / "mascot.png"
    mascot.write_bytes(b"fake")
    _make_long_db(v2_db)
    _env(monkeypatch, v3_db)
    monkeypatch.setattr(canary, "visuals_enabled", lambda: True)
    monkeypatch.setattr(canary, "select_mascot_asset", lambda **kwargs: ("base_friendly", str(mascot)))
    monkeypatch.setattr(canary, "MaxClient", ImageAndTextFailClient)
    monkeypatch.setattr("sys.argv", ["v3_controlled_send_canary.py", "--execute", "--v2-db", str(v2_db), "--v2-id", "123"])

    rc = canary.main()
    out = capsys.readouterr().out

    assert rc == 1
    assert "send_status=failed_main_send" in out
    assert "primary_send_error=image upload HTTP 500" in out
    assert "fallback_send_error=text send HTTP 502" in out
    assert "send_error=text send HTTP 502" in out
    assert "v2_send_failed_quarantined=true" in out
    assert _state(v2_db) == ("send_failed", 0, "")
