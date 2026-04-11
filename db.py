import os
import logging
import pytz
import sys
import libsql
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

IS_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"

USE_TURSO = bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)
USE_TURSO_DIRECT = USE_TURSO and IS_GITHUB_ACTIONS

DROP_TTL_HOURS = int(os.getenv("DROP_TTL_HOURS") or "48")
DIGEST_TTL_DAYS = int(os.getenv("DIGEST_TTL_DAYS") or "5")
SENT_TTL_DAYS = int(os.getenv("SENT_TTL_DAYS") or "30")
PENDING_TTL_DAYS = int(os.getenv("PENDING_TTL_DAYS") or "7")

if IS_GITHUB_ACTIONS and not USE_TURSO:
    logger.error("FATAL: TURSO_DATABASE_URL or TURSO_AUTH_TOKEN not set in GitHub Actions")
    sys.exit(1)

def _create_connection():
    if USE_TURSO_DIRECT:
        return libsql.connect(
            TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )
    elif USE_TURSO:
        return libsql.connect(
            "news_queue.db",
            sync_url=TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN
        )
    else:
        return libsql.connect("news_queue.db")

def _execute(query: str, params: tuple = ()):
    conn = _create_connection()
    try:
        result = conn.execute(query, params)
        conn.commit()
        if USE_TURSO_DIRECT:
            conn.close()
        return result
    except Exception as e:
        logger.warning(f"DB execute failed: {e}")
        if USE_TURSO_DIRECT:
            try:
                conn.close()
            except:
                pass
        raise

def _fetch_all(query: str, params: tuple = ()):
    conn = _create_connection()
    cursor = conn.execute(query, params)
    result = cursor.fetchall()
    if USE_TURSO_DIRECT:
        try:
            conn.close()
        except:
            pass
    return result

def _fetch_one(query: str, params: tuple = ()):
    conn = _create_connection()
    cursor = conn.execute(query, params)
    result = cursor.fetchone()
    if USE_TURSO_DIRECT:
        try:
            conn.close()
        except:
            pass
    return result

def init_db():
    conn = _create_connection()
    logger.info("Database backend: libsql")
    
    if USE_TURSO_DIRECT:
        try:
            conn.sync()
        except Exception as e:
            logger.warning(f"DB initial sync failed: {e}")
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            raw_text TEXT,
            processed_text TEXT,
            link TEXT NOT NULL,
            source TEXT,
            importance TEXT DEFAULT 'normal',
            category TEXT DEFAULT 'general',
            score INTEGER DEFAULT 0,
            priority_bucket TEXT DEFAULT 'low',
            reason_tags TEXT,
            is_published INTEGER DEFAULT 0,
            in_digest INTEGER DEFAULT 0,
            content_hash TEXT,
            seller_decision TEXT DEFAULT 'pending',
            seller_relevance_score INTEGER DEFAULT 0,
            actionability_score INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    try:
        conn.execute('ALTER TABLE news ADD COLUMN content_hash TEXT')
    except Exception as e:
        logger.info(f"content_hash column: {e}")
    
    try:
        conn.execute('ALTER TABLE news ADD COLUMN seller_decision TEXT DEFAULT \'pending\'')
    except:
        pass
    
    try:
        conn.execute('ALTER TABLE news ADD COLUMN seller_relevance_score INTEGER DEFAULT 0')
    except:
        pass
    
    try:
        conn.execute('ALTER TABLE news ADD COLUMN actionability_score INTEGER DEFAULT 0')
    except:
        pass
    
    try:
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_content_hash ON news(content_hash)')
        logger.info("DEBUG DB: content_hash unique index created")
    except Exception as e:
        logger.warning(f"DEBUG DB: content_hash index creation skipped: {e}")
    
    try:
        conn.execute('CREATE INDEX IF NOT EXISTS idx_link ON news(link)')
    except:
        pass
    
    try:
        conn.execute('CREATE INDEX IF NOT EXISTS idx_pending ON news(is_published, created_at)')
    except:
        pass
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS news_rejects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            raw_text TEXT,
            link TEXT NOT NULL,
            source TEXT,
            content_hash TEXT,
            seller_decision TEXT,
            seller_relevance_score INTEGER DEFAULT 0,
            actionability_score INTEGER DEFAULT 0,
            seller_reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    try:
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_rejects_content_hash ON news_rejects(content_hash)')
    except:
        pass
    
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
    conn.commit()
    conn.close()
    logger.info("Database tables initialized")

def compute_content_hash(title: str, link: str) -> str:
    normalized = f"{title.strip().lower()}|{link.strip().lower()}"
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]

def add_to_queue(title: str, raw_text: str, link: str, source: str, 
                 importance: str = "normal", category: str = "general") -> bool:
    content_hash = compute_content_hash(title, link)
    try:
        _execute(
            '''INSERT OR IGNORE INTO news (title, raw_text, link, source, importance, category, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (title, raw_text, link, source, importance, category, content_hash)
        )
        return True
    except Exception as e:
        logger.warning(f"add_to_queue failed: {e}")
        return False

def add_to_queue_batch(items: List[Dict], seller_decisions: Dict[str, Dict] = None) -> int:
    if not items:
        return 0
    
    if seller_decisions is None:
        seller_decisions = {}
    
    logger.info(f"add_to_queue_batch called with {len(items)} items")
    title_short = ""
    count = 0
    last_link = ""
    for item in items:
        try:
            raw_text = item.get('description', '') or item.get('title', '')
            score = item.get('score', 0)
            priority_bucket = item.get('priority_bucket', 'low')
            reason_tags = item.get('reason_tags', '')
            title_short = item.get('title', '')[:50]
            link = item.get('link', '')
            last_link = link
            content_hash = compute_content_hash(item.get('title', ''), link)
            
            seller_info = seller_decisions.get(link, {})
            seller_decision = seller_info.get('decision', 'pending')
            seller_relevance = seller_info.get('seller_relevance_score', 0)
            actionability = seller_info.get('actionability_score', 0)
            
            is_published = 1 if seller_decision == 'publish' else 0
            in_digest = 1 if seller_decision in ['digest', 'publish'] else 0
            
            _execute(
                '''INSERT OR IGNORE INTO news 
                   (title, raw_text, link, source, importance, category, score, priority_bucket, reason_tags, content_hash, seller_decision, seller_relevance_score, actionability_score, is_published, in_digest)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    item.get('title', ''),
                    raw_text,
                    link,
                    item.get('source', ''),
                    item.get('importance', 'normal'),
                    item.get('category', 'general'),
                    score,
                    priority_bucket,
                    reason_tags,
                    content_hash,
                    seller_decision,
                    seller_relevance,
                    actionability,
                    is_published,
                    in_digest
                )
            )
            count += 1
            if count <= 3:
                logger.info(f"Inserted item {count}: {title_short}")
        except Exception as e:
            logger.warning(f"Insert failed for {title_short}: {e}")
            continue
    
    logger.info(f"add_to_queue_batch completed, {count} items inserted")
    
    if count > 0:
        try:
            row = _fetch_one('SELECT COUNT(*) FROM news WHERE is_published = 0')
            logger.info(f"Pending count after write: {row[0] if row else 0}")
        except Exception as e:
            logger.warning(f"Pending count check failed: {e}")
    
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
    try:
        row = _fetch_one('SELECT COUNT(*) FROM news WHERE is_published = 0')
        return row[0] if row else 0
    except:
        return 0

def mark_published(news_id: int):
    _execute('UPDATE news SET is_published = 1 WHERE id = ?', (news_id,))

def mark_dropped(news_ids: List[int]):
    """Mark items as dropped so cleanup can remove them."""
    if not news_ids:
        return
    placeholders = ','.join('?' * len(news_ids))
    _execute(f"UPDATE news SET seller_decision = 'drop' WHERE id IN ({placeholders})", tuple(news_ids))

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

def get_digest_candidates(limit: int = 5) -> List[Dict]:
    MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    today = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d')
    
    try:
        rows = _fetch_all(
            '''SELECT id, title, raw_text, link, source, importance, category, score, priority_bucket, reason_tags, created_at
               FROM news
               WHERE is_published = 0 
               AND (seller_decision = 'digest' OR seller_decision IS NULL OR seller_decision = '')
               AND date(created_at) = ?
               ORDER BY 
                   CASE importance 
                       WHEN 'critical' THEN 1 
                       WHEN 'high' THEN 2 
                       WHEN 'normal' THEN 3 
                       ELSE 4 
                   END,
                   seller_relevance_score DESC,
                   score DESC
               LIMIT ?''', (today, limit)
        )
    except:
        rows = _fetch_all(
            '''SELECT id, title, raw_text, link, source, importance, category, score, priority_bucket, reason_tags, created_at
               FROM news
               WHERE is_published = 0 
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

def clean_duplicates() -> int:
    conn = _create_connection()
    try:
        cursor = conn.execute('''
            SELECT content_hash, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
            FROM news
            WHERE content_hash IS NOT NULL AND content_hash != ''
            GROUP BY content_hash
            HAVING cnt > 1
        ''')
        duplicates = cursor.fetchall()
        
        total_removed = 0
        for dup in duplicates:
            content_hash, cnt, ids = dup[0], dup[1], dup[2]
            id_list = [int(x) for x in ids.split(',')]
            
            conn.execute('UPDATE news SET is_published = 1 WHERE id = ?', (id_list[0],))
            conn.execute('DELETE FROM news WHERE id IN (SELECT id FROM news WHERE content_hash = ? AND id != ?)', (content_hash, id_list[0]))
            
            logger.info(f"Cleaned duplicates: kept id={id_list[0]}, removed {len(id_list)-1} for hash={content_hash[:8]}")
            total_removed += len(id_list) - 1
        
        conn.commit()
        conn.close()
        return total_removed
    except Exception as e:
        logger.warning(f"clean_duplicates failed: {e}")
        try:
            conn.close()
        except:
            pass
        return 0

def get_duplicate_count() -> int:
    try:
        row = _fetch_one('''
            SELECT COUNT(*) FROM (
                SELECT content_hash FROM news
                WHERE content_hash IS NOT NULL AND content_hash != '' AND is_published = 0
                GROUP BY content_hash HAVING COUNT(*) > 1
            )
        ''')
        return row[0] if row else 0
    except:
        return 0

def cleanup_by_retention_policy() -> Dict[str, int]:
    """Удаляет старые записи по TTL политике. Возвращает словарь с количеством удаленных по типам."""
    MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    now = datetime.now(MOSCOW_TZ)
    results = {}
    
    try:
        drop_cutoff = (now - timedelta(hours=DROP_TTL_HOURS)).strftime('%Y-%m-%d %H:%M:%S')
        row = _fetch_one("SELECT COUNT(*) FROM news WHERE seller_decision = 'drop' AND created_at < ?", (drop_cutoff,))
        drop_count = row[0] if row else 0
        if drop_count > 0:
            _execute("DELETE FROM news WHERE seller_decision = 'drop' AND created_at < ?", (drop_cutoff,))
            results['drop'] = drop_count
            logger.info(f"Cleanup: removed {drop_count} drop items")
        
        digest_cutoff = (now - timedelta(days=DIGEST_TTL_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
        row = _fetch_one("SELECT COUNT(*) FROM news WHERE seller_decision = 'digest' AND created_at < ?", (digest_cutoff,))
        digest_count = row[0] if row else 0
        if digest_count > 0:
            _execute("DELETE FROM news WHERE seller_decision = 'digest' AND created_at < ?", (digest_cutoff,))
            results['digest'] = digest_count
            logger.info(f"Cleanup: removed {digest_count} digest items")
        
        pending_cutoff = (now - timedelta(days=PENDING_TTL_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
        row = _fetch_one("SELECT COUNT(*) FROM news WHERE is_published = 0 AND created_at < ?", (pending_cutoff,))
        pending_count = row[0] if row else 0
        if pending_count > 0:
            _execute("DELETE FROM news WHERE is_published = 0 AND created_at < ?", (pending_cutoff,))
            results['pending'] = pending_count
            logger.info(f"Cleanup: removed {pending_count} stale pending items")
        
        sent_cutoff = (now - timedelta(days=SENT_TTL_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
        row = _fetch_one("SELECT COUNT(*) FROM news WHERE is_published = 1 AND created_at < ?", (sent_cutoff,))
        sent_count = row[0] if row else 0
        if sent_count > 0:
            _execute("DELETE FROM news WHERE is_published = 1 AND created_at < ?", (sent_cutoff,))
            results['sent'] = sent_count
            logger.info(f"Cleanup: removed {sent_count} sent items")
        
        reject_cutoff = (now - timedelta(hours=DROP_TTL_HOURS)).strftime('%Y-%m-%d %H:%M:%S')
        row = _fetch_one("SELECT COUNT(*) FROM news_rejects WHERE created_at < ?", (reject_cutoff,))
        reject_count = row[0] if row else 0
        if reject_count > 0:
            _execute("DELETE FROM news_rejects WHERE created_at < ?", (reject_cutoff,))
            results['rejects'] = reject_count
            logger.info(f"Cleanup: removed {reject_count} reject items")
        
        total = sum(results.values())
        logger.info(f"Cleanup summary: total removed {total}")
        
    except Exception as e:
        logger.warning(f"Cleanup failed: {e}")
    
    return results

def save_to_rejects(item: Dict, seller_info: Dict):
    """Сохраняет отклоненную новость в таблицу news_rejects"""
    try:
        content_hash = compute_content_hash(item.get('title', ''), item.get('link', ''))
        _execute(
            '''INSERT OR IGNORE INTO news_rejects 
               (title, raw_text, link, source, content_hash, seller_decision, seller_relevance_score, actionability_score, seller_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                item.get('title', ''),
                item.get('description', '') or item.get('raw_text', ''),
                item.get('link', ''),
                item.get('source', ''),
                content_hash,
                seller_info.get('decision', 'drop'),
                seller_info.get('seller_relevance_score', 0),
                seller_info.get('actionability_score', 0),
                seller_info.get('reason', '')
            )
        )
        logger.info(f"Reject store: saved drop item hash={content_hash[:8]}")
    except Exception as e:
        logger.warning(f"Failed to save to rejects: {e}")