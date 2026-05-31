#!/usr/bin/env python3
import os, sqlite3, tempfile, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "channel_status_check.py"

def mkdb(path, with_news=True):
    conn = sqlite3.connect(path)
    if with_news:
        conn.execute("CREATE TABLE news (id INTEGER PRIMARY KEY,title TEXT,raw_text TEXT,seller_decision TEXT,is_published INTEGER,created_at TEXT,full_article_published_at TEXT,seller_relevance_score INTEGER,actionability_score INTEGER)")
    conn.commit(); conn.close()

def run(db, clog, plog, extra_env=None):
    env = os.environ.copy()
    env.update({"MAX_BOT_TOKEN":"t","CHANNEL_ID":"c"})
    if extra_env: env.update(extra_env)
    return subprocess.check_output([sys.executable, str(SCRIPT), "--db", str(db), "--collector-log", str(clog), "--publisher-log", str(plog)], text=True, env=env, cwd=ROOT)

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    clog=td/"collector.log"; plog=td/"publisher.log"; clog.write_text("ok"); plog.write_text("ok")

    db=td/"a.db"; mkdb(db)
    conn=sqlite3.connect(db); conn.execute("INSERT INTO news VALUES (1,'t','txt','ignore',1,datetime('now'),datetime('now'),0,0)"); conn.commit(); conn.close()
    out=run(db,clog,plog); assert "CHANNEL_STATUS=OK" in out or "CHANNEL_STATUS=OK_NO_NEWS" in out; assert 'daily_min_target=' in out

    db2=td/"b.db"; mkdb(db2)
    conn=sqlite3.connect(db2); conn.execute("INSERT INTO news VALUES (1,'t','селлер','publish',0,datetime('now'),NULL,0,0)"); conn.commit(); conn.close()
    out=run(db2,clog,plog); assert "CHANNEL_STATUS=OK" in out

    out=run(td/"missing.db",clog,plog); assert "CHANNEL_STATUS=BROKEN" in out


    # should not report OK_NO_NEWS when seller-like candidates exist after minimum
    db5=td/"e.db"; mkdb(db5)
    conn=sqlite3.connect(db5)
    for i in range(1,11):
        conn.execute("INSERT INTO news VALUES (?, 'p', '', 'publish', 1, datetime('now'), datetime('now'),0,0)", (300+i,))
    conn.execute("INSERT INTO news VALUES (1,'seller update','seller changes','digest',0,datetime('now'),NULL,2,2)")
    conn.commit(); conn.close()
    out=run(db5,clog,plog)
    assert 'CHANNEL_STATUS=OK_NO_NEWS' not in out
    assert 'CHANNEL_STATUS=WARN_PUBLISHABLE_CANDIDATES' in out

    db3=td/"c.db"; mkdb(db3,with_news=False)
    out=run(db3,clog,plog); assert "CHANNEL_STATUS=BROKEN" in out

    db4=td/"d.db"; mkdb(db4)
    old=time.time()-60*60*24
    os.utime(clog,(old,old))
    out=run(db4,clog,plog); assert "CHANNEL_STATUS=WARN" in out

    clog.write_text("recent")
    os.utime(clog,None)
    plog.write_text("ERROR_SEND fail")
    out=run(db4,clog,plog); assert "CHANNEL_STATUS=BROKEN" in out or "CHANNEL_STATUS=WARN" in out

print("OK: channel_status regression checks passed")

# target should always be weekday/weekend policy
out=run(db,clog,plog)
assert ('daily_min_target=10' in out) or ('daily_min_target=3' in out)
