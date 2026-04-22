#!/usr/bin/env python3
import sqlite3

try:
    conn = sqlite3.connect('news_queue.db')
    cur = conn.cursor()
    cur.execute('SELECT id, title, link, source FROM news ORDER BY id DESC LIMIT 5')
    rows = cur.fetchall()
    conn.close()
    
    with open('db_output.txt', 'w', encoding='utf-8') as f:
        f.write(f"Found {len(rows)} items\n\n")
        for r in rows:
            f.write(f"ID: {r[0]}\n")
            f.write(f"Title: {r[1][:50]}\n")
            f.write(f"Link: {r[2][:80]}\n")
            f.write(f"Source: {r[3]}\n")
            f.write("---\n")
except Exception as e:
    with open('db_output.txt', 'w', encoding='utf-8') as f:
        f.write(f"Error: {e}")