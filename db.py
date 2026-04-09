import os
import logging
import pytz
import sys
import libsql
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

IS_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"

USE_TURSO = bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)

if IS_GITHUB_ACTIONS and not USE_TURSO:
    logger.error("FATAL: TURSO_DATABASE_URL or TURSO_AUTH_TOKEN not set in GitHub Actions")
    sys.exit(1)

_connection = None

def _get_connection():
    global _connection
    if _connection is None:
        sync_url = TURSO_DATABASE_URL if USE_TURSO else None
        auth_token = TURSO_AUTH_TOKEN if USE_TURSO else None
        _connection = libsql.connect(
            "news_queue.db",
            sync_url=sync_url,
            auth_token=auth_token
        )
        logger.info("Database connection initialized")
    return _connection

def _execute(query: str, params: tuple = ()):
    conn = _get_connection()
    conn.execute(query, params)

def _fetch_all(query: str, params: tuple = ()):
    conn = _get_connection()
    cursor = conn.execute(query, params)
    return cursor.fetchall()

def _fetch_one(query: str, params: tuple = ()):
    conn = _get_connection()
    cursor = conn.execute(query, params)
    return cursor.fetchone()

def init_db():
    logger.info("DEBUG CHECKPOINT: entering init_db")
    logger.info(f"DEBUG CHECKPOINT: USE_TURSO={USE_TURSO}")
    logger.info(f"DEBUG CHECKPOINT: IS_GITHUB_ACTIONS={IS_GITHUB_ACTIONS}")
    
    conn = _get_connection()
    logger.info("Database backend: libsql")
    
    try:
        logger.info("DEBUG DB: attempting initial sync")
        conn.sync()
        logger.info("DEBUG DB: initial sync completed")
    except Exception as e:
        logger.warning(f"DEBUG DB: initial sync failed: {e}")
    
    conn.execute('''
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
    conn.execute('''
        CREATE TABLE IF NOT EXISTS digest_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            morning_sent_date TEXT,
            evening_sent_date TEXT,
            audio_sent_date TEXT,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('INSERT OR IGNORE INTO digest_state (id) VALUES (1)')
    logger.info("Database tables initialized")

def add_to_queue(title: str, raw_text: str, link: str, source: str, 
                 importance: str = "normal", category: str = "general") -> bool:
    try:
        _execute(
            '''INSERT OR IGNORE INTO news (title, raw_text, link, source, importance, category)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (title, raw_text, link, source, importance, category)
        )
        return True
    except Exception as e:
        logger.warning(f"add_to_queue failed: {e}")
        return False

def add_to_queue_batch(items: List[Dict]) -> int:
    if not items:
        return 0
    
    logger.info(f"DEBUG DB: add_to_queue_batch called with {len(items)} items")
    title_short = ""
    count = 0
    for item in items:
        try:
            raw_text = item.get('description', '') or item.get('title', '')
            score = item.get('score', 0)
            priority_bucket = item.get('priority_bucket', 'low')
            reason_tags = item.get('reason_tags', '')
            title_short = item.get('title', '')[:50]
            
            _execute(
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
            if count <= 3:
                logger.info(f"DEBUG DB: inserted item {count}: {title_short}")
        except Exception as e:
            logger.warning(f"DEBUG DB: insert failed for {title_short}: {e}")
            continue
    
    logger.info(f"DEBUG DB: add_to_queue_batch completed, {count} items inserted")
    return count

def get_pending_news(count: int = 2) -> List[Dict]:
    rows = _fetch_all(
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
    logger.info("DEBUG DB: get_all_pending_count called")
    try:
        row = _fetch_one('SELECT COUNT(*) FROM news WHERE is_published = 0')
        logger.info(f"DEBUG DB: get_all_pending_count result: {row[0] if row else 0}")
        return row[0] if row else 0
    except Exception as e:
        logger.exception(f"DEBUG DB ERROR: get_all_pending_count failed: {e}")
        raise

def mark_published(news_id: int):
    _execute('UPDATE news SET is_published = 1 WHERE id = ?', (news_id,))

def update_processed_text(news_id: int, processed_text: str):
    _execute('UPDATE news SET processed_text = ? WHERE id = ?', (processed_text, news_id))

def get_critical_news_hours(hours: int = 24) -> List[Dict]:
    MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    now = datetime.now(MOSCOW_TZ)
    from datetime import timedelta
    cutoff = (now - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    
    rows = _fetch_all(
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

def get_digest_state() -> Dict:
    row = _fetch_one(
        'SELECT morning_sent_date, evening_sent_date, audio_sent_date FROM digest_state WHERE id = 1'
    )
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
    
    if digest_type == 'morning':
        _execute(
            'UPDATE digest_state SET morning_sent_date = ?, last_updated = ? WHERE id = 1',
            (today, datetime.now(MOSCOW_TZ).isoformat())
        )
    elif digest_type == 'evening':
        _execute(
            'UPDATE digest_state SET evening_sent_date = ?, last_updated = ? WHERE id = 1',
            (today, datetime.now(MOSCOW_TZ).isoformat())
        )
    elif digest_type == 'audio':
        _execute(
            'UPDATE digest_state SET audio_sent_date = ?, last_updated = ? WHERE id = 1',
            (today, datetime.now(MOSCOW_TZ).isoformat())
        )

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
    
    placeholders = ','.join(['?' for _ in news_ids])
    _execute(f'UPDATE news SET in_digest = 1 WHERE id IN ({placeholders})', tuple(news_ids))

def get_today_published() -> List[Dict]:
    MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    today = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d')
    
    rows = _fetch_all(
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

def get_top_news_for_digest(limit: int = 5) -> List[Dict]:
    MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    today = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d')
    
    rows = _fetch_all(
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