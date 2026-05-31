import os
import re
import time
import html
import sqlite3
import logging
from datetime import datetime

import requests

from publisher import clean_outgoing_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("full_article_callback_worker")

API_BASE = "https://platform-api.max.ru"
DB_PATH = os.getenv("NEWSBOT_DB_PATH", "/opt/newsbot_v2/news_queue.db")
POLL_TIMEOUT = int(os.getenv("MAX_UPDATES_TIMEOUT", "30"))
SLEEP_ON_ERROR = int(os.getenv("FULL_ARTICLE_WORKER_ERROR_SLEEP", "5"))


def get_token():
    token = os.getenv("MAX_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("MAX_BOT_TOKEN is empty")
    return token


def headers():
    return {
        "Authorization": get_token(),
        "Content-Type": "application/json",
    }


def api_get(path, params=None):
    resp = requests.get(
        API_BASE + path,
        params=params or {},
        headers=headers(),
        timeout=POLL_TIMEOUT + 10,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"GET {path} failed: HTTP {resp.status_code}: {resp.text[:1000]}")
    return resp.json()


def api_post(path, params=None, payload=None):
    resp = requests.post(
        API_BASE + path,
        params=params or {},
        json=payload or {},
        headers=headers(),
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"POST {path} failed: HTTP {resp.status_code}: {resp.text[:1000]}")
    try:
        return resp.json()
    except Exception:
        return {"ok": True, "raw_text": resp.text}


def api_put(path, params=None, payload=None):
    resp = requests.put(
        API_BASE + path,
        params=params or {},
        json=payload or {},
        headers=headers(),
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"PUT {path} failed: HTTP {resp.status_code}: {resp.text[:1000]}")
    try:
        return resp.json()
    except Exception:
        return {"ok": True, "raw_text": resp.text}


def answer_callback(callback_id, notification):
    if not callback_id:
        return
    try:
        api_post(
            "/answers",
            params={"callback_id": callback_id},
            payload={"notification": notification[:200]},
        )
    except Exception as e:
        logger.warning("answer_callback failed: %s", e)


def extract_updates(data):
    if isinstance(data, dict):
        for key in ("updates", "items", "data"):
            if isinstance(data.get(key), list):
                return data[key]
    if isinstance(data, list):
        return data
    return []


def get_update_marker(update):
    if not isinstance(update, dict):
        return None
    for key in ("update_id", "marker", "timestamp", "ts"):
        if update.get(key) is not None:
            return update.get(key)
    return None


def get_callback(update):
    if not isinstance(update, dict):
        return None

    if update.get("update_type") == "message_callback" or update.get("type") == "message_callback":
        return update.get("callback") or update.get("message_callback") or update

    cb = update.get("callback")
    if isinstance(cb, dict):
        return cb

    return None


def get_payload(callback):
    if not isinstance(callback, dict):
        return ""

    for key in ("payload", "data"):
        if callback.get(key):
            return str(callback.get(key))

    button = callback.get("button")
    if isinstance(button, dict) and button.get("payload"):
        return str(button.get("payload"))

    return ""


def get_callback_id(callback):
    if not isinstance(callback, dict):
        return ""
    for key in ("callback_id", "id"):
        if callback.get(key):
            return str(callback.get(key))
    return ""


def clean_full_text(text):
    text = html.unescape(text or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def build_full_article_message(row):
    news_id, title, raw_text, link, source, _max_message_id = row

    title = clean_full_text(title)
    body = clean_full_text(raw_text)

    try:
        max_chars = int(os.getenv("FULL_ARTICLE_MAX_CHARS", "3500"))
    except Exception:
        max_chars = 3500

    # MAX message limit is around 4000 chars, keep safe margin.
    header = "📖 <b>Полный текст новости</b>\n\n"
    title_part = f"<b>{title}</b>\n\n" if title else ""
    tail_parts = []
    if source:
        tail_parts.append(f"Источник: {source}")
    if link:
        tail_parts.append(link)
    tail = "\n\n" + "\n".join(tail_parts) if tail_parts else ""

    reserved = len(clean_full_text(header + title_part + tail)) + 200
    body_limit = max(500, min(max_chars, 3900 - reserved))

    if len(body) > body_limit:
        body = body[:body_limit].rstrip() + "\n\n…\n\nТекст сокращён до лимита сообщения MAX."

    msg = header + title_part + body + tail
    return clean_outgoing_text(msg)


def get_article(news_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, title, raw_text, link, source, max_message_id
        FROM news
        WHERE id = ?
        """,
        (news_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def get_max_message_id(news_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT max_message_id FROM news WHERE id = ?",
        (news_id,),
    )
    row = cur.fetchone()
    conn.close()
    return str(row[0] or "").strip() if row else ""


def increment_click(news_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE news
        SET full_article_clicks = COALESCE(full_article_clicks, 0) + 1
        WHERE id = ?
        """,
        (news_id,),
    )
    conn.commit()
    conn.close()


def already_expanded(news_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT full_article_published_at FROM news WHERE id = ?",
        (news_id,),
    )
    row = cur.fetchone()
    conn.close()
    return bool(row and row[0])


def mark_expanded(news_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE news
        SET full_article_published_at = ?,
            full_article_clicks = COALESCE(full_article_clicks, 0) + 1
        WHERE id = ?
        """,
        (datetime.utcnow().isoformat(timespec="seconds"), news_id),
    )
    conn.commit()
    conn.close()


def _seller_helper_keyboard():
    helper_bot_url = os.getenv("SELLER_HELPER_BOT_URL", "").strip()
    if not helper_bot_url:
        return None, False
    return [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {
                            "type": "link",
                            "text": "📊 Рассчитать комиссии и маржу",
                            "url": helper_bot_url,
                        }
                    ]
                ]
            },
        }
    ], True


def edit_message_to_full_article(mid, text):
    # MAX edit message endpoint.
    # The API expects message_id in query params.
    attachments, cta_present = _seller_helper_keyboard()
    payload = {
        "text": text,
        "format": "html",
        "attachments": attachments or []
    }
    result = api_put(
        "/messages",
        params={"message_id": mid},
        payload=payload,
    )
    return result, cta_present


def get_callback_message_id(callback):
    if not isinstance(callback, dict):
        return ""
    message = callback.get("message")
    if isinstance(message, dict):
        for key in ("message_id", "id"):
            if message.get(key):
                return str(message.get(key))
    for key in ("message_id", "msg_id"):
        if callback.get(key):
            return str(callback.get(key))
    return ""


def get_callback_chat_id(callback):
    if not isinstance(callback, dict):
        return ""
    message = callback.get("message")
    if isinstance(message, dict):
        for key in ("chat_id", "recipient_chat_id"):
            if message.get(key):
                return str(message.get(key))
    for key in ("chat_id", "recipient_chat_id"):
        if callback.get(key):
            return str(callback.get(key))
    return ""


def send_visible_full_article(chat_id, text):
    payload = {
        "text": text,
        "format": "html",
    }
    attachments, _ = _seller_helper_keyboard()
    if attachments:
        payload["attachments"] = attachments
    return api_post("/messages", params={"chat_id": chat_id}, payload=payload)


def expand_full_article(news_id, callback_id="", callback_message_id="", callback_chat_id=""):
    row = get_article(news_id)
    if not row:
        answer_callback(callback_id, "Не нашёл полный текст этой новости.")
        return False

    mid = get_max_message_id(news_id) or (callback_message_id or "").strip()
    logger.info("full_article_original_mid=%s", mid or "none")
    logger.info("degraded_separate_message=false")

    if already_expanded(news_id):
        increment_click(news_id)
        answer_callback(callback_id, "Полный текст уже открыт в этом посте.")
        return True

    message = build_full_article_message(row)
    if mid:
        logger.info("full_article_edit_attempt_started=true")
        try:
            _, cta_present = edit_message_to_full_article(mid, message)
            mark_expanded(news_id)
            answer_callback(callback_id, "Открыл полный текст в посте.")
            logger.info("full_article_send_mode=edit_original")
            logger.info("full_article_send_status=ok")
            logger.info("seller_helper_cta_present=%s", str(cta_present).lower())
            logger.info("Full article expanded in original message. news_id=%s mid=%s", news_id, mid)
            return True
        except Exception as e:
            logger.exception("full_article_send_status=error err=%s", e)
            logger.info("full_article_send_mode=edit_original")
            logger.info("seller_helper_cta_present=false")

    logger.info("degraded_separate_message=true")
    logger.info("full_article_send_mode=degraded_separate_message")
    logger.info("reason=no_original_message_id")
    if callback_chat_id:
        send_visible_full_article(callback_chat_id, message)
        mark_expanded(news_id)
        logger.info("full_article_send_status=ok")
        answer_callback(callback_id, "Опубликовал полный текст отдельным сообщением.")
    else:
        logger.info("full_article_send_status=error")
        answer_callback(callback_id, "Не найден ID исходного сообщения.")
    logger.warning("No editable max_message_id for news_id=%s", news_id)
    return False


def handle_update(update):
    callback = get_callback(update)
    if not callback:
        return

    payload = get_payload(callback)
    callback_id = get_callback_id(callback)

    if not payload.startswith("full_article:"):
        return

    m = re.match(r"^full_article:(\d+)$", payload.strip())
    if not m:
        answer_callback(callback_id, "Некорректная кнопка.")
        return

    news_id = int(m.group(1))
    logger.info("Full article callback received. news_id=%s callback_id=%s", news_id, callback_id)
    callback_mid = get_callback_message_id(callback)
    callback_chat_id = get_callback_chat_id(callback)
    expand_full_article(news_id, callback_id, callback_mid, callback_chat_id)


def poll_loop():
    marker = None
    logger.info("Full article callback worker started. DB=%s", DB_PATH)

    while True:
        try:
            # MAX long polling safety limits from 11.05.2026:
            # - max 2 RPS
            # - request timeout 30 sec
            # - max batch 100 events
            # - events TTL 24h
            #
            # This worker only needs callback events for the "Читать полностью" button.
            params = {
                "limit": 100,
                "timeout": POLL_TIMEOUT,
                "types": "message_callback",
            }

            if marker is not None:
                params["marker"] = marker

            data = api_get("/updates", params=params)
            updates = extract_updates(data)

            if isinstance(data, dict):
                marker = data.get("marker") or data.get("next_marker") or marker

            for upd in updates:
                handle_update(upd)
                upd_marker = get_update_marker(upd)
                if upd_marker is not None:
                    marker = upd_marker

        except KeyboardInterrupt:
            logger.info("Stopped by user")
            break
        except Exception as e:
            logger.exception("Worker error: %s", e)
            time.sleep(SLEEP_ON_ERROR)


if __name__ == "__main__":
    poll_loop()
