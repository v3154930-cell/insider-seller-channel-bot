import os
import logging
import pytz
import sys
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

IS_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"

USE_TURSO = bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)
TURSO_READY = False

if IS_GITHUB_ACTIONS and not USE_TURSO:
    logger.error("FATAL: TURSO_DATABASE_URL or TURSO_AUTH_TOKEN not set in GitHub Actions")
    sys.exit(1)

_connection = None
_local_connection = None

def _get_turso_client():
    global _connection, TURSO_READY
    if _connection is None:
        try:
            import libsql_client
            _connection = libsql_client.create_client(
                url=TURSO_DATABASE_URL,
                auth_token=TURSO_AUTH_TOKEN
            )
            TURSO_READY = True
            logger.info("Turso client initialized")
        except Exception as e:
            logger.warning(f"Failed to init Turso client: {e}, falling back to SQLite")
            return None
    return _connection

def _get_local_connection():
    global _local_connection
    import sqlite3
    if _local_connection is None:
        _local_connection = sqlite3.connect("news_queue.db", check_same_thread=False)
    return _local_connection

def get_connection():
    if USE_TURSO and TURSO_READY:
        client = _get_turso_client()
        if client:
            return client
    return _get_local_connection()

def _execute_turso(query: str, params: tuple = ()):
    client = _get_turso_client()
    if client is None:
        raise Exception("Turso not available")
    return client.execute(query, params)

def _execute_local(query: str, params: tuple = ()):
    conn = _get_local_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    return cursor

def _fetch_all_turso(query: str, params: tuple = ()):
    client = _get_turso_client()
    if client is None:
        raise Exception("Turso not available")
    result = client.execute(query, params)
    return result.rows if hasattr(result, 'rows') else []

def _fetch_all_local(query: str, params: tuple = ()):
    conn = _get_local_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor.fetchall()

def _fetch_one_turso(query: str, params: tuple = ()):
    rows = _fetch_all_turso(query, params)
    return rows[0] if rows else None

def _fetch_one_local(query: str, params: tuple = ()):
    conn = _get_local_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor.fetchone()

def init_db():
    logger.info("DEBUG CHECKPOINT: entering init_db")
    logger.info(f"DEBUG CHECKPOINT: USE_TURSO={USE_TURSO}")
    logger.info(f"DEBUG CHECKPOINT: IS_GITHUB_ACTIONS={IS_GITHUB_ACTIONS}")
    logger.info(f"DEBUG CHECKPOINT: TURSO_READY={TURSO_READY}")
    
    if IS_GITHUB_ACTIONS and USE_TURSO and not TURSO_READY:
        logger.error("FATAL: Turso client initialization failed in GitHub Actions")
        sys.exit(1)
    
    if USE_TURSO and TURSO_READY:
        client = _get_turso_client()
        if client:
            logger.info("Database backend: Turso")
            client.execute('''
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
            client.execute('''
                CREATE TABLE IF NOT EXISTS digest_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    morning_sent_date TEXT,
                    evening_sent_date TEXT,
                    audio_sent_date TEXT,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            client.execute('INSERT OR IGNORE INTO digest_state (id) VALUES (1)')
            logger.info("Turso tables initialized")
            return
    else:
        logger.info("Database backend: SQLite fallback")
    
    conn = _get_local_connection()
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
    logger.info("Local SQLite tables initialized")

def add_to_queue(title: str, raw_text: str, link: str, source: str, 
                 importance: str = "normal", category: str = "general") -> bool:
    if USE_TURSO and TURSO_READY:
        try:
            result = _execute_turso(
                '''INSERT OR IGNORE INTO news (title, raw_text, link, source, importance, category)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (title, raw_text, link, source, importance, category)
            )
            return True
        except Exception:
            return False
    else:
        conn = _get_local_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                '''INSERT OR IGNORE INTO news (title, raw_text, link, source, importance, category)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (title, raw_text, link, source, importance, category)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False

def add_to_queue_batch(items: List[Dict]) -> int:
    if not items:
        return 0
    
    if USE_TURSO and TURSO_READY:
        count = 0
        for item in items:
            try:
                raw_text = item.get('description', '') or item.get('title', '')
                score = item.get('score', 0)
                priority_bucket = item.get('priority_bucket', 'low')
                reason_tags = item.get('reason_tags', '')
                
                result = _execute_turso(
                    '''INSERT OR IGNORE INTO news 
                       (title, raw_text, link, source, importance, category, score, priority_bucket, reason_tags)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        item.get('title', ''),
                        raw_text,
                        item.get('link', ''),
                        item.get('source', ''),
                        item.get('importance', 'normal'),
                        item.get('category', 'general'),
                        score,
                        priority_bucket,
                        reason_tags
                    )
                )
                count += 1
            except Exception:
                continue
        return count
    else:
        conn = _get_local_connection()
        cursor = conn.cursor()
        count = 0
        for item in items:
            try:
                raw_text = item.get('description', '') or item.get('title', '')
                score = item.get('score', 0)
                priority_bucket = item.get('priority_bucket', 'low')
                reason_tags = item.get('reason_tags', '')
                
                cursor.execute(
                    '''INSERT OR IGNORE INTO news 
                       (title, raw_text, link, source, importance, category, score, priority_bucket, reason_tags)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        item.get('title', ''),
                        raw_text,
                        item.get('link', ''),
                        item.get('source', ''),
                        item.get('importance', 'normal'),
                        item.get('category', 'general'),
                        score,
                        priority_bucket,
                        reason_tags
                    )
                )
                if cursor.rowcount > 0:
                    count += 1
            except Exception:
                continue
        conn.commit()
        return count

def get_pending_news(count: int = 2) -> List[Dict]:
    if USE_TURSO and TURSO_READY:
        rows = _fetch_all_turso(
            '''SELECT id, title, raw_text, processed_text, link, source, importance, category, 
                      score, priority_bucket, reason_tags, created_at
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
               LIMIT ?''', (count,)
        )
        news_list = []
        for row in rows:
            news_list.append({
                'id': row[0],
                'title': row[1],
                'raw_text': row[2] or '',
                'description': row[2] or '',
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
    else:
        conn = _get_local_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT id, title, raw_text, processed_text, link, source, importance, category, 
                      score, priority_bucket, reason_tags, created_at
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
               LIMIT ?''', (count,)
        )
        rows = cursor.fetchall()
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
    if USE_TURSO and TURSO_READY:
        row = _fetch_one_turso('SELECT COUNT(*) FROM news WHERE is_published = 0')
        return row[0] if row else 0
    else:
        conn = _get_local_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM news WHERE is_published = 0')
        return cursor.fetchone()[0]

def mark_published(news_id: int):
    if USE_TURSO and TURSO_READY:
        _execute_turso('UPDATE news SET is_published = 1 WHERE id = ?', (news_id,))
    else:
        conn = _get_local_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE news SET is_published = 1 WHERE id = ?', (news_id,))
        conn.commit()

def update_processed_text(news_id: int, processed_text: str):
    if USE_TURSO and TURSO_READY:
        _execute_turso('UPDATE news SET processed_text = ? WHERE id = ?', (processed_text, news_id))
    else:
        conn = _get_local_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE news SET processed_text = ? WHERE id = ?', (processed_text, news_id))
        conn.commit()

def get_critical_news_hours(hours: int = 24) -> List[Dict]:
    if USE_TURSO and TURSO_READY:
        MOSCOW_TZ = pytz.timezone('Europe/Moscow')
        now = datetime.now(MOSCOW_TZ)
        from datetime import timedelta
        cutoff = (now - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        
        rows = _fetch_all_turso(
            '''SELECT id, title, raw_text, link, source, importance, category, created_at
               FROM news
               WHERE is_published = 1 
               AND created_at >= ?
               AND importance IN ('critical', 'high')
               ORDER BY created_at DESC''', (cutoff,)
        )
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
    else:
        conn = _get_local_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT id, title, raw_text, link, source, importance, category, created_at
               FROM news
               WHERE is_published = 1 
               AND created_at >= datetime('now', '-' || ? || ' hours')
               AND importance IN ('critical', 'high')
               ORDER BY created_at DESC''', (hours,)
        )
        rows = cursor.fetchall()
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
    if USE_TURSO and TURSO_READY:
        row = _fetch_one_turso(
            'SELECT morning_sent_date, evening_sent_date, audio_sent_date FROM digest_state WHERE id = 1'
        )
        if row:
            return {
                'morning_sent_date': row[0],
                'evening_sent_date': row[1],
                'audio_sent_date': row[2]
            }
        return {'morning_sent_date': None, 'evening_sent_date': None, 'audio_sent_date': None}
    else:
        conn = _get_local_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT morning_sent_date, evening_sent_date, audio_sent_date FROM digest_state WHERE id = 1')
        row = cursor.fetchone()
        if row:
            return {
                'morning_sent_date': row[0],
                'evening_sent_date': row[1],
                'audio_sent_date': row[2]
            }
        return {'morning_sent_date': None, 'evening_sent_date': None, 'audio_sent_date': None}

def set_digest_sent(digest_type: str):
    MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    today = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d')
    
    if USE_TURSO and TURSO_READY:
        if digest_type == 'morning':
            _execute_turso(
                'UPDATE digest_state SET morning_sent_date = ?, last_updated = ? WHERE id = 1',
                (today, datetime.now(MOSCOW_TZ).isoformat())
            )
        elif digest_type == 'evening':
            _execute_turso(
                'UPDATE digest_state SET evening_sent_date = ?, last_updated = ? WHERE id = 1',
                (today, datetime.now(MOSCOW_TZ).isoformat())
            )
        elif digest_type == 'audio':
            _execute_turso(
                'UPDATE digest_state SET audio_sent_date = ?, last_updated = ? WHERE id = 1',
                (today, datetime.now(MOSCOW_TZ).isoformat())
            )
    else:
        conn = _get_local_connection()
        cursor = conn.cursor()
        if digest_type == 'morning':
            cursor.execute(
                'UPDATE digest_state SET morning_sent_date = ?, last_updated = ? WHERE id = 1',
                (today, datetime.now().isoformat())
            )
        elif digest_type == 'evening':
            cursor.execute(
                'UPDATE digest_state SET evening_sent_date = ?, last_updated = ? WHERE id = 1',
                (today, datetime.now().isoformat())
            )
        elif digest_type == 'audio':
            cursor.execute(
                'UPDATE digest_state SET audio_sent_date = ?, last_updated = ? WHERE id = 1',
                (today, datetime.now().isoformat())
            )
        conn.commit()

def is_digest_sent_today(digest_type: str) -> bool:
    MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    today = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d')
    state = get_digest_state()
    
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
    
    if USE_TURSO and TURSO_READY:
        placeholders = ','.join(['?' for _ in news_ids])
        _execute_turso(f'UPDATE news SET in_digest = 1 WHERE id IN ({placeholders})', tuple(news_ids))
    else:
        conn = _get_local_connection()
        cursor = conn.cursor()
        placeholders = ','.join(['?' for _ in news_ids])
        cursor.execute(f'UPDATE news SET in_digest = 1 WHERE id IN ({placeholders})', tuple(news_ids))
        conn.commit()

def get_today_published() -> List[Dict]:
    if USE_TURSO and TURSO_READY:
        MOSCOW_TZ = pytz.timezone('Europe/Moscow')
        today = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d')
        
        rows = _fetch_all_turso(
            '''SELECT id, title, raw_text, link, source, importance, category, created_at
               FROM news
               WHERE is_published = 1 
               AND date(created_at) = ?
               ORDER BY created_at DESC''', (today,)
        )
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
    else:
        conn = _get_local_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT id, title, raw_text, link, source, importance, category, created_at
               FROM news
               WHERE is_published = 1 
               AND date(created_at) = date('now')
               ORDER BY created_at DESC'''
        )
        rows = cursor.fetchall()
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
    if USE_TURSO and TURSO_READY:
        MOSCOW_TZ = pytz.timezone('Europe/Moscow')
        today = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d')
        
        rows = _fetch_all_turso(
            '''SELECT id, title, raw_text, link, source, importance, category, score, priority_bucket, reason_tags, created_at
               FROM news
               WHERE is_published = 1 
               AND in_digest = 0
               AND date(created_at) = ?
               ORDER BY 
                   CASE importance 
                       WHEN 'critical' THEN 1 
                       WHEN 'high' THEN 2 
                       WHEN 'normal' THEN 3 
                       ELSE 4 
                   END,
                   score DESC
               LIMIT ?''', (today, limit)
        )
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
    else:
        conn = _get_local_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT id, title, raw_text, link, source, importance, category, score, priority_bucket, reason_tags, created_at
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
               LIMIT ?''', (limit,)
        )
        rows = cursor.fetchall()
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