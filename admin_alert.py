#!/usr/bin/env python3
import argparse
import os
import sqlite3
import json
import hashlib
from datetime import datetime, date
from pathlib import Path

import requests

BASE_DIR = Path("/opt/newsbot_v2")
NEWS_DB = BASE_DIR / "news_queue.db"
TARIFF_DB = BASE_DIR / "data" / "unified_tariffs.db"
ENV_PATH = BASE_DIR / ".env"

DEFAULT_ADMIN_CHAT_ID = "220878972"
DEFAULT_API_BASE = "https://botapi.max.ru"


def load_env():
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def table_exists(cur, table_name):
    row = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def get_ozon_status():
    result = {
        "status": "red",
        "status_label": "нужна ручная проверка",
        "source_file": "не найден",
        "source_status": "не указан",
        "source_role": "не указан",
        "valid_from": "",
        "rows": 0,
        "created_at": "",
        "age_days": None,
        "signals_after_source": 0,
        "select_status": "не найден",
    }

    if not TARIFF_DB.exists():
        result["status_label"] = "unified_tariffs.db не найден"
        return result

    try:
        conn = sqlite3.connect(TARIFF_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if table_exists(cur, "tariff_source_quality"):
            row = cur.execute("""
                SELECT source_file, source_status, source_role, created_at
                FROM tariff_source_quality
                WHERE marketplace = 'ozon'
                  AND source_role = 'standard_marketplace_service_rate'
                ORDER BY created_at DESC
                LIMIT 1
            """).fetchone()

            if row:
                result["source_file"] = row["source_file"] or "не найден"
                result["source_status"] = row["source_status"] or "не указан"
                result["source_role"] = row["source_role"] or "не указан"
                result["created_at"] = row["created_at"] or ""

            select_row = cur.execute("""
                SELECT source_status
                FROM tariff_source_quality
                WHERE marketplace = 'ozon'
                  AND (
                    lower(source_file) LIKE '%select%'
                    OR lower(source_note) LIKE '%select%'
                    OR lower(comment) LIKE '%select%'
                    OR source_file LIKE '%Селект%'
                    OR source_note LIKE '%Селект%'
                    OR comment LIKE '%Селект%'
                  )
                ORDER BY created_at DESC
                LIMIT 1
            """).fetchone()

            if select_row:
                result["select_status"] = select_row["source_status"] or "найден"

        if table_exists(cur, "clean_commissions"):
            row = cur.execute("""
                SELECT COUNT(*) AS rows_count, MAX(valid_from) AS valid_from
                FROM clean_commissions
                WHERE marketplace = 'ozon'
                  AND fee_type = 'marketplace_service_rate'
                  AND (
                    ? = 'не найден'
                    OR source_file = ?
                  )
            """, (result["source_file"], result["source_file"])).fetchone()

            if row:
                result["rows"] = int(row["rows_count"] or 0)
                result["valid_from"] = row["valid_from"] or ""

        conn.close()

    except Exception as e:
        result["status_label"] = f"ошибка чтения тарифной базы: {e}"
        return result

    if result["valid_from"]:
        try:
            d = datetime.strptime(result["valid_from"], "%Y-%m-%d").date()
            result["age_days"] = (date.today() - d).days
        except Exception:
            pass

    since = ""
    if result["created_at"]:
        since = result["created_at"][:10]
    elif result["valid_from"]:
        since = result["valid_from"]

    try:
        conn = sqlite3.connect(NEWS_DB)
        cur = conn.cursor()

        if since and table_exists(cur, "tariff_signals"):
            row = cur.execute("""
                SELECT COUNT(*)
                FROM tariff_signals
                WHERE marketplace = 'ozon'
                  AND substr(detected_at, 1, 10) > ?
                  AND signal_level IN ('high', 'medium')
                  AND signal_type IN (
                    'tariff',
                    'logistics',
                    'returns',
                    'storage',
                    'api'
                  )
                  AND (
                    source LIKE 'OFFICIAL:%'
                    OR source LIKE 'Ozon%'
                    OR source LIKE 'OZON%'
                    OR source LIKE 'Seller API%'
                  )
                  AND lower(COALESCE(title, '')) NOT LIKE '%скидк%'
                  AND lower(COALESCE(title, '')) NOT LIKE '%банк%'
                  AND lower(COALESCE(title, '')) NOT LIKE '%брошенн%'
                  AND lower(COALESCE(title, '')) NOT LIKE '%кейс%'
            """, (since,)).fetchone()

            result["signals_after_source"] = int(row[0] or 0) if row else 0

        conn.close()
    except Exception:
        pass

    if result["source_file"] == "не найден" or result["rows"] <= 0:
        result["status"] = "red"
        result["status_label"] = "нужна ручная загрузка Ozon"
    elif result["source_status"] != "usable":
        result["status"] = "red"
        result["status_label"] = "боевой Ozon-источник не usable"
    elif result["signals_after_source"] > 0:
        result["status"] = "yellow"
        result["status_label"] = "есть Ozon-сигналы после загрузки"
    elif result["age_days"] is not None and result["age_days"] > 30:
        # Возраст Ozon-файла сам по себе больше не является поводом
        # ежедневно тревожить админа, если источник usable, строки есть,
        # и новых actionable Ozon-сигналов после загрузки нет.
        result["status"] = "green"
        result["status_label"] = "Ozon-источник usable; новых actionable сигналов нет"
    else:
        result["status"] = "green"
        result["status_label"] = "Ozon-источник свежий"

    return result


def get_official_layer_today():
    result = {
        "rows_today": 0,
        "docs": [],
    }

    try:
        conn = sqlite3.connect(NEWS_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if not table_exists(cur, "rules_documents"):
            conn.close()
            return result

        today = date.today().strftime("%Y-%m-%d")

        row = cur.execute("""
            SELECT COUNT(*)
            FROM rules_documents
            WHERE substr(loaded_at, 1, 10) = ?
        """, (today,)).fetchone()

        result["rows_today"] = int(row[0] or 0) if row else 0

        rows = cur.execute("""
            SELECT marketplace, document_name, COUNT(*) AS rows_loaded
            FROM rules_documents
            WHERE substr(loaded_at, 1, 10) = ?
            GROUP BY marketplace, document_name
            ORDER BY rows_loaded DESC
            LIMIT 5
        """, (today,)).fetchall()

        result["docs"] = [dict(x) for x in rows]
        conn.close()

    except Exception:
        pass

    return result



def ensure_admin_alert_state_table():
    conn = sqlite3.connect(TARIFF_DB)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_alert_state (
                alert_key TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_sent_at TEXT,
                sent_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
    finally:
        conn.close()


def make_admin_alert_fingerprint(reasons, ozon, official):
    payload = {
        "reasons": list(reasons or []),
        "ozon": {
            "status": ozon.get("status"),
            "status_label": ozon.get("status_label"),
            "source_file": ozon.get("source_file"),
            "source_status": ozon.get("source_status"),
            "valid_from": ozon.get("valid_from"),
            "rows": ozon.get("rows"),
            "signals_after_source": ozon.get("signals_after_source"),
        },
        # official layer is informational only, not an alert trigger
        "official_rows_today": official.get("rows_today"),
    }

    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def should_send_admin_alert(alert_key, reasons, ozon, official):
    """
    Возвращает True только если:
    - такого alert_key ещё не было;
    - изменился fingerprint проблемы;
    Иначе обновляет last_seen_at и молчит.
    """
    ensure_admin_alert_state_table()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fingerprint = make_admin_alert_fingerprint(reasons, ozon, official)

    conn = sqlite3.connect(TARIFF_DB)
    conn.row_factory = sqlite3.Row

    try:
        row = conn.execute(
            "SELECT * FROM admin_alert_state WHERE alert_key=?",
            (alert_key,),
        ).fetchone()

        if not row:
            conn.execute("""
                INSERT INTO admin_alert_state(
                    alert_key, fingerprint, first_seen_at, last_seen_at, last_sent_at, sent_count
                )
                VALUES (?, ?, ?, ?, ?, 1)
            """, (alert_key, fingerprint, now, now, now))
            conn.commit()
            return True

        if row["fingerprint"] != fingerprint:
            conn.execute("""
                UPDATE admin_alert_state
                SET fingerprint=?,
                    last_seen_at=?,
                    last_sent_at=?,
                    sent_count=sent_count+1
                WHERE alert_key=?
            """, (fingerprint, now, now, alert_key))
            conn.commit()
            return True

        conn.execute("""
            UPDATE admin_alert_state
            SET last_seen_at=?
            WHERE alert_key=?
        """, (now, alert_key))
        conn.commit()
        return False

    finally:
        conn.close()


def build_message(force=False):
    ozon = get_ozon_status()
    official = get_official_layer_today()

    reasons = []

    if ozon["status"] in ("yellow", "red"):
        reasons.append(f"Ozon: {ozon['status_label']}")

    # ВАЖНО:
    # Сам факт обновления official/rules_documents больше НЕ является поводом
    # ежедневно тревожить админа. Это нормальная работа мониторинга.
    # Админ-алерт должен уходить только по проблемам/изменению статуса.
    # official["rows_today"] можно показывать в force-режиме или в админке,
    # но не использовать как самостоятельную причину предупреждения.

    if not reasons and not force:
        return None

    if reasons and not force:
        if not should_send_admin_alert(
            alert_key="admin_alert:official_sources",
            reasons=reasons,
            ozon=ozon,
            official=official,
        ):
            return None

    lines = []
    lines.append("⚠️ <b>Проверь админку Инсайдер Селлер</b>")
    lines.append("")
    lines.append("Есть административные сигналы по официальным источникам.")
    lines.append("")

    if reasons:
        lines.append("<b>Почему:</b>")
        for r in reasons:
            lines.append(f"• {r}")
        lines.append("")
    else:
        lines.append("Это тестовое уведомление.")
        lines.append("")

    lines.append("<b>Ozon:</b>")
    lines.append(f"• статус: {ozon['status_label']}")
    lines.append(f"• файл: {ozon['source_file']}")
    lines.append(f"• valid_from: {ozon['valid_from'] or 'не указано'}")
    lines.append(f"• строк marketplace_service_rate: {ozon['rows']}")
    lines.append(f"• Ozon-сигналы после загрузки: {ozon['signals_after_source']}")
    lines.append(f"• Ozon Select: {ozon['select_status']} — не использовать как боевой источник")
    lines.append("")

    if official["docs"]:
        lines.append("<b>Официальный слой сегодня:</b>")
        for d in official["docs"][:5]:
            mp = d.get("marketplace") or "unknown"
            doc = d.get("document_name") or "документ"
            cnt = int(d.get("rows_loaded") or 0)
            lines.append(f"• {mp}: {doc} — {cnt} строк")
        lines.append("")

    admin_url = os.getenv("ADMIN_URL") or os.getenv("NEWSBOT_ADMIN_URL") or ""
    if admin_url:
        lines.append(f"Админка: {admin_url}")
    else:
        lines.append("Открой админку NEWSBOT v2 и проверь блок «Свежесть официальных источников».")

    return "\n".join(lines)


def send_to_admin(text):
    load_env()

    token = os.getenv("ADMIN_ALERT_BOT_TOKEN") or os.getenv("MAX_BOT_TOKEN")
    chat_id = (
        os.getenv("ADMIN_ALERT_CHAT_ID")
        or os.getenv("MAX_ADMIN_CHAT_ID")
        or DEFAULT_ADMIN_CHAT_ID
    )

    api_base = os.getenv("MAX_API_BASE") or DEFAULT_API_BASE

    if not token:
        raise RuntimeError("MAX_BOT_TOKEN не найден в .env")

    if not chat_id:
        raise RuntimeError("ADMIN_ALERT_CHAT_ID / MAX_ADMIN_CHAT_ID не задан")

    url = f"{api_base}/messages?chat_id={chat_id}"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "format": "html",
        "disable_link_preview": False,
    }

    r = requests.post(url, headers=headers, json=payload, timeout=30)

    if r.status_code != 200:
        raise RuntimeError(f"MAX send failed: {r.status_code} {r.text}")

    return r.text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="Send alert to MAX admin chat")
    parser.add_argument("--force", action="store_true", help="Send even if no attention required")
    args = parser.parse_args()

    load_env()

    msg = build_message(force=args.force)

    if not msg:
        print("ADMIN_ALERT: no attention required")
        return

    print("=== ADMIN ALERT MESSAGE ===")
    print(msg)

    if args.send:
        result = send_to_admin(msg)
        print("ADMIN_ALERT: sent")
        print(result)
    else:
        print("ADMIN_ALERT: dry run only. Use --send to send.")


if __name__ == "__main__":
    main()
