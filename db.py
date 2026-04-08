import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional

DB_FILE = "news_queue.db"

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            raw_text TEXT,
            processed_text TEXT,
            link TEXT UNIQUE NOT NULL,
            source TEXT,
            importance TEXT DEFAULT 'normal',
            category TEXT DEFAULT 'general',
            is_published INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_to_queue(title: str, raw_text: str, link: str, source: str, 
                 importance: str = "normal", category: str = "general") -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO news (title, raw_text, link, source, importance, category)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, raw_text, link, source, importance, category))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error:
        return False
    finally:
        conn.close()

def add_to_queue_batch(items: List[Dict]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    count = 0
    for item in items:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO news (title, raw_text, link, source, importance, category)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                item.get('title', ''),
                item.get('description', ''),
                item.get('link', ''),
                item.get('source', ''),
                item.get('importance', 'normal'),
                item.get('category', 'general')
            ))
            if cursor.rowcount > 0:
                count += 1
        except sqlite3.Error:
            continue
    conn.commit()
    conn.close()
    return count

def get_pending_news(count: int = 2) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, raw_text, processed_text, link, source, importance, category, created_at
        FROM news
        WHERE is_published = 0
        ORDER BY 
            CASE importance 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                ELSE 3 
            END,
            created_at ASC
        LIMIT ?
    ''', (count,))
    rows = cursor.fetchall()
    conn.close()
    
    news_list = []
    for row in rows:
        news_list.append({
            'id': row[0],
            'title': row[1],
            'raw_text': row[2] if row[2] else '',
            'processed_text': row[3],
            'link': row[4],
            'source': row[5],
            'importance': row[6],
            'category': row[7],
            'created_at': row[8]
        })
    return news_list

def get_all_pending_count() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM news WHERE is_published = 0')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def mark_published(news_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE news SET is_published = 1 WHERE id = ?', (news_id,))
    conn.commit()
    conn.close()

def update_processed_text(news_id: int, processed_text: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE news SET processed_text = ? WHERE id = ?', (processed_text, news_id))
    conn.commit()
    conn.close()

def get_critical_news_hours(hours: int = 24) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, raw_text, link, source, importance, category, created_at
        FROM news
        WHERE is_published = 1 
        AND created_at >= datetime('now', '-' || ? || ' hours')
        AND importance IN ('critical', 'high')
        ORDER BY created_at DESC
    ''', (hours,))
    rows = cursor.fetchall()
    conn.close()
    
    news_list = []
    for row in rows:
        news_list.append({
            'id': row[0],
            'title': row[1],
            'raw_text': row[2],
            'link': row[3],
            'source': row[4],
            'importance': row[5],
            'category': row[6],
            'created_at': row[7]
        })
    return news_list

def get_today_published() -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, raw_text, link, source, importance, category, created_at
        FROM news
        WHERE is_published = 1 
        AND date(created_at) = date('now')
        ORDER BY created_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    news_list = []
    for row in rows:
        news_list.append({
            'id': row[0],
            'title': row[1],
            'raw_text': row[2],
            'link': row[3],
            'source': row[4],
            'importance': row[5],
            'category': row[6],
            'created_at': row[7]
        })
    return news_list