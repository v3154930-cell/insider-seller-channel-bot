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
            score INTEGER DEFAULT 0,
            priority_bucket TEXT DEFAULT 'low',
            reason_tags TEXT,
            is_published INTEGER DEFAULT 0,
            in_digest INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS digest_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            morning_sent_date TEXT,
            evening_sent_date TEXT,
            audio_sent_date TEXT,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('INSERT OR IGNORE INTO digest_state (id) VALUES (1)')
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
            raw_text = item.get('description', '') or item.get('title', '')
            score = item.get('score', 0)
            priority_bucket = item.get('priority_bucket', 'low')
            reason_tags = item.get('reason_tags', '')
            
            cursor.execute('''
                INSERT OR IGNORE INTO news (title, raw_text, link, source, importance, category, score, priority_bucket, reason_tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item.get('title', ''),
                raw_text,
                item.get('link', ''),
                item.get('source', ''),
                item.get('importance', 'normal'),
                item.get('category', 'general'),
                score,
                priority_bucket,
                reason_tags
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
        SELECT id, title, raw_text, processed_text, link, source, importance, category, score, priority_bucket, reason_tags, created_at
        FROM news
        WHERE is_published = 0
        ORDER BY 
            CASE importance 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                ELSE 3 
            END,
            score DESC,
            created_at ASC
        LIMIT ?
    ''', (count,))
    rows = cursor.fetchall()
    conn.close()
    
    news_list = []
    for row in rows:
        raw_t = row[2] if row[2] else ''
        news_list.append({
            'id': row[0],
            'title': row[1],
            'raw_text': raw_t,
            'description': raw_t,
            'processed_text': row[3],
            'link': row[4],
            'source': row[5],
            'importance': row[6],
            'category': row[7],
            'score': row[8],
            'priority_bucket': row[9],
            'reason_tags': row[10],
            'created_at': row[11]
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

def get_digest_state() -> Dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT morning_sent_date, evening_sent_date, audio_sent_date FROM digest_state WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'morning_sent_date': row[0],
            'evening_sent_date': row[1],
            'audio_sent_date': row[2]
        }
    return {'morning_sent_date': None, 'evening_sent_date': None, 'audio_sent_date': None}

def set_digest_sent(digest_type: str):
    conn = get_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    
    if digest_type == 'morning':
        cursor.execute('UPDATE digest_state SET morning_sent_date = ?, last_updated = ? WHERE id = 1', (today, datetime.now().isoformat()))
    elif digest_type == 'evening':
        cursor.execute('UPDATE digest_state SET evening_sent_date = ?, last_updated = ? WHERE id = 1', (today, datetime.now().isoformat()))
    elif digest_type == 'audio':
        cursor.execute('UPDATE digest_state SET audio_sent_date = ?, last_updated = ? WHERE id = 1', (today, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

def is_digest_sent_today(digest_type: str) -> bool:
    state = get_digest_state()
    today = datetime.now().strftime('%Y-%m-%d')
    
    if digest_type == 'morning':
        return state.get('morning_sent_date') == today
    elif digest_type == 'evening':
        return state.get('evening_sent_date') == today
    elif digest_type == 'audio':
        return state.get('audio_sent_date') == today
    return False

def mark_news_in_digest(news_ids: List[int]):
    if not news_ids:
        return
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ','.join(['?'] * len(news_ids))
    cursor.execute(f'UPDATE news SET in_digest = 1 WHERE id IN ({placeholders})', news_ids)
    conn.commit()
    conn.close()

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

def get_top_news_for_digest(limit: int = 5) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, raw_text, link, source, importance, category, score, priority_bucket, reason_tags, created_at
        FROM news
        WHERE is_published = 1 
        AND in_digest = 0
        AND date(created_at) = date('now')
        ORDER BY 
            CASE importance 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                WHEN 'normal' THEN 3 
                ELSE 4 
            END,
            score DESC
        LIMIT ?
    ''', (limit,))
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
            'score': row[7],
            'priority_bucket': row[8],
            'reason_tags': row[9],
            'created_at': row[10]
        })
    return news_list
