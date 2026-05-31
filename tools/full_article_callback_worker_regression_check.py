#!/usr/bin/env python3
import os
import sqlite3
import tempfile
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

import full_article_callback_worker as w


def mkdb(path):
    conn = sqlite3.connect(path)
    conn.execute('''CREATE TABLE news (id INTEGER PRIMARY KEY, title TEXT, raw_text TEXT, link TEXT, source TEXT, max_message_id TEXT, full_article_published_at TEXT, full_article_clicks INTEGER DEFAULT 0)''')
    conn.execute("INSERT INTO news (id,title,raw_text,link,source,max_message_id) VALUES (1,'T','Body '*200,'http://x','src','stored_mid_1')")
    conn.commit(); conn.close()

with tempfile.TemporaryDirectory() as td:
    db = Path(td)/'news.db'
    mkdb(db)
    w.DB_PATH = str(db)

    calls = []
    edits = []
    w.send_visible_full_article = lambda t, v, m: calls.append((t, str(v))) or {"ok": True}
    w.edit_message_to_full_article = lambda mid, text: edits.append(str(mid)) or {"ok": True}
    w.answer_callback = lambda *a, **k: None

    assert w.expand_full_article(1, "cb1", update={"chat_id": 123}, callback={"payload": "full_article:1"}) is True
    assert calls[-1] == ("chat_id", "123")

    conn = sqlite3.connect(db); conn.execute("UPDATE news SET full_article_published_at=NULL WHERE id=1"); conn.commit(); conn.close()
    assert w.expand_full_article(1, "cb2", update={"message": {"recipient": {"dialog_id": "dlg42"}}}, callback={"payload": "full_article:1"}) is True
    assert calls[-1] == ("dialog_id", "dlg42")

    calls.clear(); edits.clear()
    conn = sqlite3.connect(db); conn.execute("UPDATE news SET full_article_published_at=NULL,max_message_id='stored_mid_1' WHERE id=1"); conn.commit(); conn.close()
    assert w.expand_full_article(1, "cb3", update={"message": {"body": {"mid": "cb_mid_77"}}}, callback={"payload": "full_article:1"}) is True
    assert edits[-1] == "cb_mid_77"

    conn = sqlite3.connect(db); conn.execute("UPDATE news SET full_article_published_at=NULL,max_message_id='stored_mid_9' WHERE id=1"); conn.commit(); conn.close()
    assert w.expand_full_article(1, "cb4", update={}, callback={"payload": "full_article:1"}) is True
    assert edits[-1] == "stored_mid_9"

    conn = sqlite3.connect(db); conn.execute("UPDATE news SET full_article_published_at=NULL,max_message_id='' WHERE id=1"); conn.commit(); conn.close()
    assert w.expand_full_article(1, "cb5", update={}, callback={"payload": "full_article:1"}) is False

    cands, mid = w.extract_delivery_targets({"dialog_id": "d1", "message": {"recipient": {"chat_id": 55}, "body": {"mid": "m9"}}}, {"sender": {"user_id": "u2"}})
    assert any(t == "dialog_id" and v == "d1" for _, t, v in cands)
    assert any(t == "chat_id" and v == "55" for _, t, v in cands)
    assert any(t == "user_id" and v == "u2" for _, t, v in cands)
    assert mid == "m9"

    from stable_publisher_v3 import extract_message_id
    assert extract_message_id({"message": {"body": {"mid": "n1"}}}) == "n1"
    assert extract_message_id({"message": {"id": "n2"}}) == "n2"
    assert extract_message_id({"body": {"mid": "n3"}}) == "n3"
    assert extract_message_id({"message_id": "n4"}) == "n4"

print("OK: full_article_callback_worker regression checks passed")
