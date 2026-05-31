#!/usr/bin/env python3
import sqlite3
from datetime import datetime, date

DB = "/opt/newsbot_v2/news_queue.db"
today = date.today().isoformat()
since = today + " 00:00:00"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

def one(sql, params=()):
    return con.execute(sql, params).fetchone()[0]

print("NEWSBOT HEALTH", datetime.now().isoformat(timespec="seconds"))

print("published_today:", one("""
    SELECT COUNT(*) FROM news
    WHERE is_published=1 AND seller_decision='publish' AND created_at >= ?
""", (since,)))

print("pending_publish:", one("""
    SELECT COUNT(*) FROM news
    WHERE IFNULL(is_published,0)=0 AND seller_decision='publish'
"""))

print("pending_digest:", one("""
    SELECT COUNT(*) FROM news
    WHERE IFNULL(is_published,0)=0 AND seller_decision='digest'
"""))

print("strong_ignore_today:", one("""
    SELECT COUNT(*) FROM news
    WHERE created_at >= ?
      AND IFNULL(is_published,0)=0
      AND seller_decision='ignore'
      AND score >= 70
""", (since,)))

print("latest_created:", one("SELECT COALESCE(MAX(created_at),'none') FROM news"))

print("\nlatest pending publish:")
for r in con.execute("""
    SELECT id, created_at, source, score, title
    FROM news
    WHERE IFNULL(is_published,0)=0 AND seller_decision='publish'
    ORDER BY created_at DESC
    LIMIT 10
"""):
    print(dict(r))
