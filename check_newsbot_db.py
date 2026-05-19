import os
from db import init_db, _fetch_all

print("DATABASE_BACKEND:", os.getenv("DATABASE_BACKEND"))
print("TURSO_DATABASE_URL exists:", bool(os.getenv("TURSO_DATABASE_URL")))

init_db()

print("\n=== TABLES ===")
try:
    tables = _fetch_all("""
        SELECT name 
        FROM sqlite_master 
        WHERE type='table'
        ORDER BY name
    """)
    for t in tables:
        print(t)
except Exception as e:
    print("tables check failed:", repr(e))

print("\n=== news_queue CHECK ===")
try:
    rows = _fetch_all("SELECT COUNT(*) AS cnt FROM news_queue")
    print("news_queue rows:", rows[0]["cnt"])
except Exception as e:
    print("news_queue failed:", repr(e))

print("\n=== news CHECK ===")
try:
    rows = _fetch_all("SELECT COUNT(*) AS cnt FROM news")
    print("news rows:", rows[0]["cnt"])
except Exception as e:
    print("news failed:", repr(e))
