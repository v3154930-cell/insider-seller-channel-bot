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
    monkeypatch.delenv("NEWSBOT_V3_SEND_MASCOT_ATTACHMENTS", raising=False)
    monkeypatch.delenv("NEWSBOT_V3_ENABLE_MASCOT_IMAGES", raising=False)


def _make_db(path, rows):
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
    con.executemany(
        "INSERT INTO news VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    con.commit()
    con.close()


def _decision(path, news_id):
    con = sqlite3.connect(path)
    row = con.execute(
        "SELECT seller_decision, COALESCE(is_published,0), COALESCE(max_message_id,'') FROM news WHERE id=?",
        (news_id,),
    ).fetchone()
    con.close()
    return row


class FailingClient:
    @classmethod
    def from_env(cls, target_channel=""):
        return cls()

    def diagnostics(self):
        return {"max_mode": "limited_live", "max_guard_ok": True}

    def send_text(self, *args, **kwargs):
        raise canary.MaxClientSendError("boom text send")

    def send_text_with_callback_button(self, *args, **kwargs):
        raise canary.MaxClientSendError("boom callback send")

    def extract_message_id(self, response):
        return response.get("message_id")

    def validate_visible_delivery(self, response):
        return bool(response.get("message_id"))


def test_failed_main_send_quarantines_v2_candidate(monkeypatch, tmp_path, capsys):
    v2_db = tmp_path / "v2.db"
    v3_db = tmp_path / "v3.db"
    _make_db(
        v2_db,
        [(123, "WB тариф для селлеров", "body", "https://e.test/123", "src", "2026-05-29T10:00:00", "publish", 6, 6, 0, None)],
    )
    _env(monkeypatch, v3_db)
    monkeypatch.setattr(canary, "MaxClient", FailingClient)
    monkeypatch.setattr("sys.argv", ["v3_controlled_send_canary.py", "--execute", "--v2-db", str(v2_db), "--v2-id", "123"])

    rc = canary.main()
    out = capsys.readouterr().out

    assert rc == 1
    assert "send_status=failed_main_send" in out
    assert "send_error=boom text send" in out
    assert "primary_send_error=boom text send" in out
    assert "v2_send_failed_quarantined=true" in out
    assert "v2_send_failed_decision=send_failed" in out
    assert _decision(v2_db, 123) == ("send_failed", 0, "")


def test_failed_candidate_does_not_block_next_candidate(monkeypatch, tmp_path, capsys):
    v2_db = tmp_path / "v2.db"
    v3_db = tmp_path / "v3.db"
    _make_db(
        v2_db,
        [
            (123, "WB тариф для селлеров", "body", "https://e.test/123", "src", "2026-05-29T10:00:00", "publish", 6, 6, 0, None),
            (124, "Ozon комиссия для продавцов", "body", "https://e.test/124", "src", "2026-05-29T11:00:00", "publish", 6, 6, 0, None),
        ],
    )
    _env(monkeypatch, v3_db)
    monkeypatch.setattr(canary, "MaxClient", FailingClient)
    monkeypatch.setattr("sys.argv", ["v3_controlled_send_canary.py", "--execute", "--v2-db", str(v2_db), "--v2-id", "123"])
    assert canary.main() == 1
    capsys.readouterr()

    monkeypatch.setattr("sys.argv", ["v3_controlled_send_canary.py", "--v2-db", str(v2_db)])
    rc = canary.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "selected_candidate_id=candidate-v2-124" in out
    assert "candidate-v2-123" not in out
    assert _decision(v2_db, 123)[0] == "send_failed"


def test_already_published_candidate_is_not_quarantined(tmp_path):
    v2_db = tmp_path / "v2.db"
    _make_db(
        v2_db,
        [(123, "WB тариф", "body", "https://e.test/123", "src", "2026-05-29T10:00:00", "publish", 6, 6, 1, "mid-already")],
    )

    changed = canary._quarantine_v2_send_failed(str(v2_db), "123", "boom")

    assert changed is False
    assert _decision(v2_db, 123) == ("publish", 1, "mid-already")


def test_safety_promote_does_not_treat_minimum_as_maximum(monkeypatch, tmp_path, capsys):
    from newsbot_v2 import safety_promote_ignored_to_publish_v1 as promote

    db = tmp_path / "queue.db"
    con = sqlite3.connect(db)
    con.execute(
        """
        CREATE TABLE news(
            id INTEGER PRIMARY KEY,
            created_at TEXT,
            source TEXT,
            score INTEGER,
            title TEXT,
            raw_text TEXT,
            seller_decision TEXT,
            seller_relevance_score INTEGER,
            actionability_score INTEGER,
            is_published INTEGER,
            max_message_id TEXT
        )
        """
    )
    today = promote.date.today().isoformat()
    published_rows = [
        (i, f"{today} 10:{i:02d}:00", "src", 10, f"published {i}", "", "publish", 6, 6, 1, f"mid-{i}")
        for i in range(1, 11)
    ]
    con.executemany("INSERT INTO news VALUES(?,?,?,?,?,?,?,?,?,?,?)", published_rows)
    con.execute(
        "INSERT INTO news VALUES(99, ?, 'src', 99, 'WB тариф для селлеров', 'важная новость wildberries продавец комиссия', 'digest', 0, 0, 0, '')",
        (f"{today} 12:00:00",),
    )
    con.execute(
        "INSERT INTO news VALUES(100, ?, 'src', 100, 'send failed must stay failed', 'wildberries продавец', 'send_failed', 0, 0, 0, '')",
        (f"{today} 13:00:00",),
    )
    con.commit()
    con.close()

    monkeypatch.setattr(promote, "DB", str(db))

    promote.main()
    out = capsys.readouterr().out

    assert "SKIP target reached" not in out
    assert "INFO daily minimum already satisfied published_today=10 target=10" in out
    assert "selected=[99]" in out
    con = sqlite3.connect(db)
    decisions = dict(con.execute("SELECT id, seller_decision FROM news WHERE id IN (99,100)").fetchall())
    con.close()
    assert decisions == {99: "publish", 100: "send_failed"}
