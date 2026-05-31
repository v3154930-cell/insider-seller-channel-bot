#!/usr/bin/env python3
import os, sqlite3, tempfile, subprocess, sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
env = os.environ.copy()
env["PYTHONPATH"] = str(root)

with tempfile.TemporaryDirectory() as td:
    db = Path(td) / "news.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE news (id INTEGER PRIMARY KEY,title TEXT,processed_text TEXT,raw_text TEXT,source TEXT,link TEXT,seller_decision TEXT,is_published INTEGER DEFAULT 0,created_at TEXT,full_article_published_at TEXT,max_message_id TEXT,seller_relevance_score INTEGER,actionability_score INTEGER,score INTEGER)""")
    conn.execute("INSERT INTO news (id,title,processed_text,raw_text,source,link,seller_decision,is_published,created_at,seller_relevance_score,actionability_score,score) VALUES (1,'Title1','Body1','Body1','src','http://x','publish',0,datetime('now'),5,5,5)")
    conn.execute("INSERT INTO news (id,title,processed_text,raw_text,source,link,seller_decision,is_published,created_at) VALUES (2,'E','тариф для селлера','тариф для селлера','src','http://y','digest',0,datetime('now'))")
    for i in (10,11,12):
        conn.execute("INSERT INTO news (id,title,processed_text,raw_text,source,link,seller_decision,is_published,created_at,full_article_published_at) VALUES (?, 'p','','','s','','publish',1,datetime('now'),datetime('now'))", (i,))
    conn.commit(); conn.close()

    cmd=[sys.executable, str(root/'stable_publisher_v3.py'),'--dry-run']
    base={**env, "NEWS_DB_PATH":str(db), "SELLER_HELPER_BOT_URL":"https://max.ru/id", "ENABLE_SELLER_HELPER_CTA":"true"}
    out=subprocess.check_output(cmd, text=True, env=base, cwd=root)
    assert 'selected_reason=direct_publish' in out
    assert 'published_today=3' in out and 'daily_cap_applied=false' in out and 'batch_size=1' in out
    assert 'helper_cta_preview_start' in out and 'helper_cta_button_url_present=true' in out

    no_url={**base, "SELLER_HELPER_BOT_URL":"", "HELPER_BOT_URL":""}
    out2=subprocess.check_output(cmd, text=True, env=no_url, cwd=root)
    assert 'helper_cta_button_url_present=false' in out2 and 'helper_cta_status=dry_run' in out2

    from stable_publisher_v3 import build_post, build_seller_helper_cta_text
    item={"title":"Ozon сам говорит","processed_text":"Ozon сам говорит\nДля половины пользователей\nДля селлера\nдля онлайн-продаж","source":"s","link":"l"}
    post=build_post(item)
    assert post.count("Ozon сам говорит")==1 and "Для половины пользователей" in post and "Для селлера" in post and "айн-покупке" not in post
    assert "Проверить комиссию и прибыль" in build_seller_helper_cta_text()



    # after daily minimum met, low-value blue emergency candidate must be skipped
    db_low = Path(td) / "low.db"
    conn = sqlite3.connect(db_low)
    conn.execute("""CREATE TABLE news (id INTEGER PRIMARY KEY,title TEXT,processed_text TEXT,raw_text TEXT,source TEXT,link TEXT,seller_decision TEXT,is_published INTEGER DEFAULT 0,created_at TEXT,full_article_published_at TEXT,max_message_id TEXT,seller_relevance_score INTEGER,actionability_score INTEGER,score INTEGER)""")
    for i in range(1,11):
        conn.execute("INSERT INTO news (id,title,processed_text,raw_text,source,link,seller_decision,is_published,created_at,full_article_published_at) VALUES (?, 'p','','','s','','publish',1,datetime('now'),datetime('now'))", (100+i,))
    conn.execute("INSERT INTO news (id,title,processed_text,raw_text,source,link,seller_decision,is_published,created_at) VALUES (1,'Нейтральная новость','Просто обновление','Просто обновление','src','http://z','digest',0,datetime('now'))")
    conn.commit(); conn.close()
    out3=subprocess.check_output(cmd, text=True, env={**base, "NEWS_DB_PATH":str(db_low)}, cwd=root)
    assert 'selected_reason=skipped_low_value_after_min' in out3
    assert 'fallback_candidates_seen=1' in out3
    assert 'fallback_candidates_skipped_low_value=1' in out3

    assert out3.count("candidate_importance=") == 1
    assert out3.count("candidate_skip_reason=") == 1

    # before daily minimum, blue emergency candidate may be selected
    db_pre = Path(td) / "pre.db"
    conn = sqlite3.connect(db_pre)
    conn.execute("""CREATE TABLE news (id INTEGER PRIMARY KEY,title TEXT,processed_text TEXT,raw_text TEXT,source TEXT,link TEXT,seller_decision TEXT,is_published INTEGER DEFAULT 0,created_at TEXT,full_article_published_at TEXT,max_message_id TEXT,seller_relevance_score INTEGER,actionability_score INTEGER,score INTEGER)""")
    conn.execute("INSERT INTO news (id,title,processed_text,raw_text,source,link,seller_decision,is_published,created_at) VALUES (1,'Нейтральная новость','Просто обновление','Просто обновление','src','http://z','digest',0,datetime('now'))")
    conn.commit(); conn.close()
    out4=subprocess.check_output(cmd, text=True, env={**base, "NEWS_DB_PATH":str(db_pre)}, cwd=root)
    assert 'selected_reason=emergency_fallback' in out4

    # red candidate after minimum can still publish
    db_red = Path(td) / "red.db"
    conn = sqlite3.connect(db_red)
    conn.execute("""CREATE TABLE news (id INTEGER PRIMARY KEY,title TEXT,processed_text TEXT,raw_text TEXT,source TEXT,link TEXT,seller_decision TEXT,is_published INTEGER DEFAULT 0,created_at TEXT,full_article_published_at TEXT,max_message_id TEXT,seller_relevance_score INTEGER,actionability_score INTEGER,score INTEGER)""")
    for i in range(1,11):
        conn.execute("INSERT INTO news (id,title,processed_text,raw_text,source,link,seller_decision,is_published,created_at,full_article_published_at) VALUES (?, 'p','','','s','','publish',1,datetime('now'),datetime('now'))", (200+i,))
    conn.execute("INSERT INTO news (id,title,processed_text,raw_text,source,link,seller_decision,is_published,created_at) VALUES (1,'WB повышает комиссию','Изменения комиссии для селлера','Изменения комиссии для селлера','src','http://r','digest',0,datetime('now'))")
    conn.commit(); conn.close()
    out5=subprocess.check_output(cmd, text=True, env={**base, "NEWS_DB_PATH":str(db_red)}, cwd=root)
    assert 'selected_reason=emergency_fallback' in out5

    # after minimum, first blue candidate must not stop scan if stronger yellow exists
    db_mix = Path(td) / "mix.db"
    conn = sqlite3.connect(db_mix)
    conn.execute("""CREATE TABLE news (id INTEGER PRIMARY KEY,title TEXT,processed_text TEXT,raw_text TEXT,source TEXT,link TEXT,seller_decision TEXT,is_published INTEGER DEFAULT 0,created_at TEXT,full_article_published_at TEXT,max_message_id TEXT,seller_relevance_score INTEGER,actionability_score INTEGER,score INTEGER)""")
    for i in range(1,11):
        conn.execute("INSERT INTO news (id,title,processed_text,raw_text,source,link,seller_decision,is_published,created_at,full_article_published_at) VALUES (?, 'p','','','s','','publish',1,datetime('now'),datetime('now'))", (400+i,))
    conn.execute("INSERT INTO news (id,title,processed_text,raw_text,source,link,seller_decision,is_published,created_at,seller_relevance_score,actionability_score) VALUES (1,'Просто новость','Нейтральный фон','Нейтральный фон','src','http://b','digest',0,datetime('now'),0,0)")
    conn.execute("INSERT INTO news (id,title,processed_text,raw_text,source,link,seller_decision,is_published,created_at,seller_relevance_score,actionability_score) VALUES (2,'Рынок маркетплейсов','аналитика для селлеров по маркетплейс','аналитика для селлеров по маркетплейс','src','http://y','ignore',0,datetime('now'),2,2)")
    conn.commit(); conn.close()
    out6=subprocess.check_output(cmd, text=True, env={**base, "NEWS_DB_PATH":str(db_mix)}, cwd=root)
    assert 'selected_reason=emergency_fallback' in out6
    assert 'selected_candidate_id=2' in out6
    assert 'fallback_candidates_seen=2' in out6
    assert out6.count("fallback_candidates_seen=") == 1

print("OK: stable_publisher_v3 regression checks passed")
