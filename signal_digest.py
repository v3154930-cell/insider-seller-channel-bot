import argparse
import html
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("/opt/newsbot_v2/news_queue.db")
ENV_PATH = Path("/opt/newsbot_v2/.env")

CHECKED_MARKETPLACES = ["Ozon", "Wildberries", "Яндекс Маркет"]

MP_LABELS = {
    "ozon": "Ozon",
    "wildberries": "Wildberries",
    "yandex_market": "Яндекс Маркет",
    "multiple": "несколько площадок",
    "unknown": "не определено",
}

IMPORTANT_TYPES = {
    "tariff": "тарифы / комиссии",
    "offer": "оферта / условия",
    "logistics": "логистика",
    "returns": "возвраты",
    "storage": "хранение / размещение",
    "payouts": "выплаты / взаиморасчёты",
    "penalties": "штрафы / удержания",
    "api": "API / кабинет продавца",
    "marking": "маркировка",
    "regulator": "регуляторика",
}

NOISE_PATTERNS = [
    "конкурс",
    "розыгрыш",
    "мерч",
    "вебинар",
    "подкаст",
    "обучение",
    "акция",
    "акции",
    "промо",
    "распродажа",
    "пвз что надо",
    "витрина магазина",
    "витрину магазина",
    "витрины магазина",
    "продаёт витрину",
    "продает витрину",
    "баннер",
]

STRICT_DROP_PATTERNS = [
    "брошенн",
    "корзин",
    "платный инструмент",
    "ии-ассистент",
    "сводк",
    "кабинет продавца",
    "в одном окне",
    "график ключевых",
    "конкурс",
    "пвз что надо",
    "витрин",
    "акци",
    "промо",
    "цены на маркетплейсах вырастут",
    "пошла подготовка",
    "товары на маркетплейсах подорожают",
    "подорожают из-за закона",
    "ozon банк",
    "озон банк",
    "проанализировал изменения способов платежей",
    "аналитики банка",
    "снегопад",
    "курьеры вовремя доставляют",
    "национальной модели торговли",
    "национальная модель торговли",
    "кейс апэт",
    "кейс апт",
    "сроками годности",
    "срок годности",
    "частный кейс",
    "платежных документов",
    "платёжных документов",
    "приказ минфина",
    "оформления платеж",
    "оформления платёж",
]


def load_env():
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def is_noise(title: str) -> bool:
    title_norm = (title or "").lower().replace("ё", "е")
    return any(pattern in title_norm for pattern in NOISE_PATTERNS)


def is_publishable_reliable_signal(item: dict) -> bool:
    """
    Строгий режим для публикации в MAX-канал.

    Публикуем только:
    1. сильные регуляторные сигналы по маркетплейсам;
    2. реальные обновления оферты/условий с датой вступления;
    3. реальные изменения тарифов/комиссий.

    Не публикуем интерфейсные обновления, банковскую аналитику,
    частные кейсы, прогнозные статьи и маркетинговые инструменты.
    """
    title = (item.get("title") or "").lower().replace("ё", "е")
    signal_types = set(item.get("signal_types") or [item.get("signal_type")])

    if any(pattern in title for pattern in STRICT_DROP_PATTERNS):
        return False

    if "фас" in title and (
        "выдала предупреждения маркетплейсам" in title
        or "предупреждения маркетплейсам" in title
        or "потребовала сократить сроки выплат" in title
        or "потребовал сократить сроки выплат" in title
        or ("предупреж" in title and "маркетплейс" in title)
    ):
        return True

    if (
        ("обновил оферту" in title or "обновила оферту" in title or "обновили оферту" in title)
        and ("вступит в силу" in title or "вступает в силу" in title or "с " in title)
    ):
        return True

    if ("tariff" in signal_types or "тариф" in title or "комисси" in title) and (
        "изменил тариф" in title
        or "изменили тариф" in title
        or "изменение тариф" in title
        or "новые тарифы" in title
        or "повышение комиссии" in title
        or "снижение комиссии" in title
        or "комиссии измен" in title
    ):
        return True

    return False


def event_dedupe_key(item: dict) -> str:
    title = (item.get("title") or "").lower().replace("ё", "е")

    if "фас" in title and ("выплат" in title or "срок" in title or "предупреж" in title):
        return "fas_marketplace_payouts_conditions"

    if "фас" in title and ("ozon" in title or "wildberries" in title or "маркетплейс" in title):
        return "fas_marketplace_conditions"

    if "обновил оферту" in title or "обновила оферту" in title or "обновили оферту" in title:
        return f"offer_update:{item.get('marketplace')}:{item.get('source')}"

    return f"news:{item.get('news_id')}"


def marketplace_icon(marketplace: str) -> str:
    return {
        "ozon": "🔵",
        "wildberries": "🟣",
        "yandex_market": "🟡",
        "multiple": "🛒",
        "unknown": "⚖️",
    }.get(marketplace or "unknown", "▫️")


def compact_signal_name(item: dict) -> str:
    title = (item.get("title") or "").lower().replace("ё", "е")
    marketplace = item.get("marketplace")

    if "фас" in title:
        if "выплат" in title:
            return "ФАС / выплаты селлерам"
        return "ФАС / условия маркетплейсов"

    if "оферт" in title:
        return "обновление оферты"

    if "тариф" in title or "комисси" in title:
        return "тарифы / комиссии"

    if "выплат" in title:
        return "выплаты / взаиморасчёты"

    if marketplace == "ozon":
        return "сигнал Ozon"
    if marketplace == "wildberries":
        return "сигнал Wildberries"
    if marketplace == "yandex_market":
        return "сигнал Яндекс Маркета"

    return "сигнал к проверке"


def clean_signal_title(title: str) -> str:
    title = (title or "").strip()
    title = title.replace("...", "…")
    title = title.replace(" .", ".")
    title = title.replace(" ,", ",")
    title = title.replace(" :", ":")
    title = " ".join(title.split())

    cuts = [
        " Причина простая:",
        " Важные изменения:",
        " Что изменилось:",
        " По факту:",
    ]

    for cut in cuts:
        if cut in title:
            title = title.split(cut)[0].strip()

    if len(title) > 230:
        title = title[:227].rstrip() + "…"

    return title


def action_line(item: dict) -> str:
    marketplace = item.get("marketplace")
    title = (item.get("title") or "").lower().replace("ё", "е")

    if "фас" in title:
        return "Проверить официальные сообщения ФАС и реакцию площадок."

    if marketplace == "ozon":
        return "Проверить официальный Excel / слой marketplace_service_rate."

    if marketplace == "wildberries":
        return "Сверить с официальной офертой WB и рабочим DB-слоем."

    if marketplace == "yandex_market":
        return "Сверить с официальной справкой/API/DB-слоем Яндекс Маркета."

    return "Проверить официальный источник перед изменением расчётов."


def get_recent_signals(limit=20):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT
            id,
            news_id,
            source,
            marketplace,
            signal_type,
            signal_level,
            title,
            link,
            published_at,
            detected_at,
            status,
            reason
        FROM tariff_signals
        WHERE status = 'new'
          AND signal_level IN ('high', 'medium')
        ORDER BY
            CASE signal_level WHEN 'high' THEN 0 ELSE 1 END,
            id DESC
        LIMIT ?
        """,
        (limit * 5,),
    ).fetchall()

    conn.close()

    grouped = {}

    for row in rows:
        item = dict(row)
        title = item.get("title") or ""

        if is_noise(title):
            continue

        news_id = item.get("news_id")

        if news_id not in grouped:
            item["signal_types"] = set([item.get("signal_type")])
            grouped[news_id] = item
        else:
            grouped[news_id]["signal_types"].add(item.get("signal_type"))

            if item.get("signal_level") == "high":
                grouped[news_id]["signal_level"] = "high"

            if grouped[news_id].get("marketplace") in ("unknown", None, "") and item.get("marketplace"):
                grouped[news_id]["marketplace"] = item.get("marketplace")

    clean = list(grouped.values())

    for item in clean:
        item["signal_types"] = sorted([s for s in item.get("signal_types", set()) if s])

    clean = [item for item in clean if is_publishable_reliable_signal(item)]

    deduped = []
    seen_events = set()

    for item in clean:
        key = event_dedupe_key(item)
        if key in seen_events:
            continue
        seen_events.add(key)
        deduped.append(item)

    priority = {
        "high": 0,
        "medium": 1,
    }

    deduped.sort(key=lambda x: (priority.get(x.get("signal_level"), 9), -int(x.get("id") or 0)))

    return deduped[:limit]



def table_exists(cur, table: str) -> bool:
    row = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def get_official_layer_updates(date_key: str):
    """
    Возвращает загрузки официального слоя за дату.
    Это не равно автоматически подтверждённому изменению условий,
    но если официальный слой обновлялся, вечерний монитор не должен писать
    "изменений нет".
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if not table_exists(cur, "rules_documents"):
        conn.close()
        return []

    rows = cur.execute(
        """
        SELECT
            marketplace,
            document_name,
            source_url,
            COUNT(*) AS rows_loaded,
            COUNT(DISTINCT section) AS sections,
            COUNT(DISTINCT content_hash) AS hashes,
            MIN(loaded_at) AS first_loaded,
            MAX(loaded_at) AS last_loaded
        FROM rules_documents
        WHERE substr(loaded_at, 1, 10) = ?
          AND COALESCE(document_name, '') != ''
        GROUP BY marketplace, document_name, source_url
        ORDER BY rows_loaded DESC, document_name
        """,
        (date_key,),
    ).fetchall()

    result = []
    for row in rows:
        item = dict(row)

        # Сравниваем с предыдущими загрузками этого же документа.
        prev = cur.execute(
            """
            SELECT
                COUNT(DISTINCT section) AS prev_sections,
                COUNT(DISTINCT content_hash) AS prev_hashes,
                MAX(substr(loaded_at, 1, 10)) AS prev_day
            FROM rules_documents
            WHERE marketplace = ?
              AND document_name = ?
              AND COALESCE(source_url, '') = COALESCE(?, '')
              AND substr(loaded_at, 1, 10) < ?
            """,
            (
                item.get("marketplace"),
                item.get("document_name"),
                item.get("source_url"),
                date_key,
            ),
        ).fetchone()

        # Более точная оценка новых/изменённых фрагментов.
        section_rows = cur.execute(
            """
            SELECT section, content_hash
            FROM rules_documents
            WHERE marketplace = ?
              AND document_name = ?
              AND COALESCE(source_url, '') = COALESCE(?, '')
              AND substr(loaded_at, 1, 10) = ?
            """,
            (
                item.get("marketplace"),
                item.get("document_name"),
                item.get("source_url"),
                date_key,
            ),
        ).fetchall()

        new_sections = 0
        changed_sections = 0
        same_sections = 0

        for sr in section_rows:
            old = cur.execute(
                """
                SELECT content_hash
                FROM rules_documents
                WHERE marketplace = ?
                  AND document_name = ?
                  AND COALESCE(source_url, '') = COALESCE(?, '')
                  AND section = ?
                  AND substr(loaded_at, 1, 10) < ?
                ORDER BY loaded_at DESC, id DESC
                LIMIT 1
                """,
                (
                    item.get("marketplace"),
                    item.get("document_name"),
                    item.get("source_url"),
                    sr["section"],
                    date_key,
                ),
            ).fetchone()

            if old is None:
                new_sections += 1
            elif old["content_hash"] != sr["content_hash"]:
                changed_sections += 1
            else:
                same_sections += 1

        item["new_sections"] = new_sections
        item["changed_sections"] = changed_sections
        item["same_sections"] = same_sections
        item["prev_day"] = prev["prev_day"] if prev else None
        result.append(item)

    conn.close()
    return result


def marketplace_display_name(mp: str) -> str:
    return {
        "ozon": "Ozon",
        "wildberries": "Wildberries",
        "wb": "Wildberries",
        "yandex_market": "Яндекс Маркет",
        "yandex": "Яндекс Маркет",
        "multiple": "несколько площадок",
        "unknown": "не определено",
    }.get(mp or "unknown", mp or "не определено")


def official_layer_digest_lines(updates, limit=6):
    lines = []
    if not updates:
        return lines

    lines.append("⚠️ <b>За день обновлялись официальные источники маркетплейсов.</b>")
    lines.append("Это не означает, что тарифы или условия уже изменены в расчётах. Команда канала сверяет обновления с официальными документами.")
    lines.append("")

    for item in updates[:limit]:
        mp = html.escape(marketplace_display_name(item.get("marketplace")))
        doc = html.escape(item.get("document_name") or "документ")
        rows_loaded = int(item.get("rows_loaded") or 0)
        changed = int(item.get("changed_sections") or 0)
        new = int(item.get("new_sections") or 0)

        details = [f"{rows_loaded} фрагментов"]
        if changed:
            details.append(f"изменённых фрагментов: {changed}")
        if new:
            details.append(f"новых фрагментов: {new}")

        lines.append(f"• <b>{mp}</b>: {doc} — {', '.join(details)}.")

    if len(updates) > limit:
        lines.append(f"• ещё документов: {len(updates) - limit}")

    lines.append("")
    lines.append("Если изменения действительно влияют на продавцов, релевантные тарифы и условия будут учтены в Seller Helper после проверки.")
    return lines

def get_official_updates(date_key=None, limit=10):
    """
    Возвращает загрузки официальных документов/тарифных источников за день.
    Это публичный сигнал: официальный источник обновлялся, но расчёты Seller Helper
    меняются только после проверки.
    """
    if date_key is None:
        date_key = today_key()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    def _table_exists(name):
        row = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (name,)
        ).fetchone()
        return row is not None

    if not _table_exists("rules_documents"):
        conn.close()
        return []

    groups = cur.execute("""
        SELECT
            marketplace,
            document_name,
            source_url,
            COUNT(*) AS rows_loaded,
            COUNT(DISTINCT section) AS sections,
            MIN(loaded_at) AS first_loaded,
            MAX(loaded_at) AS last_loaded
        FROM rules_documents
        WHERE substr(loaded_at, 1, 10) = ?
        GROUP BY marketplace, document_name, source_url
        ORDER BY rows_loaded DESC
        LIMIT ?
    """, (date_key, limit)).fetchall()

    result = []

    for g in groups:
        marketplace = g["marketplace"] or "unknown"
        document_name = g["document_name"] or "Документ"
        source_url = g["source_url"] or ""

        current_rows = cur.execute("""
            SELECT section, content_hash
            FROM rules_documents
            WHERE substr(loaded_at, 1, 10) = ?
              AND marketplace = ?
              AND COALESCE(document_name, '') = COALESCE(?, '')
              AND COALESCE(source_url, '') = COALESCE(?, '')
        """, (date_key, marketplace, document_name, source_url)).fetchall()

        new_sections = 0
        changed_sections = 0
        same_sections = 0

        for r in current_rows:
            section = r["section"] or ""
            current_hash = r["content_hash"] or ""

            prev = cur.execute("""
                SELECT content_hash
                FROM rules_documents
                WHERE loaded_at < ?
                  AND marketplace = ?
                  AND COALESCE(document_name, '') = COALESCE(?, '')
                  AND COALESCE(source_url, '') = COALESCE(?, '')
                  AND COALESCE(section, '') = COALESCE(?, '')
                ORDER BY loaded_at DESC, id DESC
                LIMIT 1
            """, (date_key + " 00:00:00", marketplace, document_name, source_url, section)).fetchone()

            if not prev:
                new_sections += 1
            elif (prev["content_hash"] or "") != current_hash:
                changed_sections += 1
            else:
                same_sections += 1

        label = MP_LABELS.get(marketplace, marketplace)

        # Человеческие названия для публичного канала
        pretty_name = document_name
        pretty_map = {
            "20260426_141822_Оферта товарная.pdf": "оферта продавца",
            "20260426_141844_marketplace-services-rates-01-04-2026.xlsx": "таблица комиссий и тарифов",
            "20260426_141811_Полный список комиссий и тарифов.pdf": "полный список комиссий и тарифов",
            "WB API — комиссии по категориям": "комиссии по категориям",
            "Яндекс Маркет — legal CPA service agreement": "договорные условия",
            "Яндекс Маркет — legal terms marketplace crossboard": "условия cross-border",
            "Яндекс Маркет — тарифы FBY": "тарифы FBY",
        }
        pretty_name = pretty_map.get(pretty_name, pretty_name)

        result.append({
            "marketplace": marketplace,
            "marketplace_label": label,
            "document_name": pretty_name,
            "rows_loaded": int(g["rows_loaded"] or 0),
            "sections": int(g["sections"] or 0),
            "new_sections": int(new_sections),
            "changed_sections_vs_previous_load": int(changed_sections),
            "changed_sections": int(changed_sections),
            "same_sections_vs_previous_load": int(same_sections),
            "first_loaded": g["first_loaded"],
            "last_loaded": g["last_loaded"],
            "source_url": source_url,
        })

    conn.close()
    return result

def build_digest(signals, official_updates=None, digest_date_key=None):
    digest_date_key = digest_date_key or today_key()
    today = datetime.strptime(digest_date_key, "%Y-%m-%d").strftime("%d.%m.%Y")
    official_updates = official_updates if official_updates is not None else get_official_layer_updates(digest_date_key)

    lines = []
    lines.append("🔎 <b>Вечерний монитор изменений</b>")
    lines.append(f"<b>Условия, тарифы и оферты маркетплейсов · {today}</b>")
    lines.append("")

    if not signals:
        if official_updates:
            lines.extend(official_layer_digest_lines(official_updates))
            lines.append("")
            lines.append("Публикуем только проверенные изменения, чтобы не вводить селлеров в заблуждение.")
            return "\n".join(lines)

        lines.append("✅ <b>Надёжных изменений за день не обнаружено.</b>")
        lines.append("")
        lines.append("Проверены направления:")
        for marketplace in CHECKED_MARKETPLACES:
            lines.append(f"• {html.escape(marketplace)}")
        lines.append("")
        lines.append("Новостные и TG-сигналы без подтверждения официальным источником не считаются изменением тарифов.")
        return "\n".join(lines)

    lines.append("⚠️ <b>Найдены сигналы, которые требуют проверки:</b>")
    lines.append("")

    for index, signal in enumerate(signals[:5], 1):
        marketplace_key = signal.get("marketplace") or "unknown"
        marketplace = MP_LABELS.get(marketplace_key, marketplace_key)
        icon = marketplace_icon(marketplace_key)
        signal_name = compact_signal_name(signal)
        level = "высокий" if signal.get("signal_level") == "high" else "средний"

        title = html.escape(clean_signal_title(signal.get("title") or ""))
        source = html.escape(signal.get("source") or "источник не указан")
        link = html.escape(signal.get("link") or "")

        lines.append(f"{icon} <b>{index}. {html.escape(marketplace)} · {html.escape(signal_name)}</b>")
        lines.append(f"Уровень: {html.escape(level)}")
        lines.append(f"Суть: {title}")
        lines.append(f"Что сделать: {html.escape(action_line(signal))}")
        lines.append(f"Источник: {source}")

        if link:
            lines.append(f"Ссылка: {link}")

        lines.append("")

    if official_updates:
        lines.append("—")
        lines.extend(official_layer_digest_lines(official_updates))

    lines.append("—")
    lines.append("ℹ️ <b>Важно:</b> сигнал сам по себе не меняет расчёт Seller Helper.")
    lines.append("Числовые тарифы обновляются только после проверки официального источника: Excel/API/DB-слоя clean_commissions.")

    return "\n".join(lines)



def today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def ensure_digest_run_table():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS signal_digest_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        digest_date TEXT UNIQUE,
        published_at TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT,
        item_count INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()


def was_digest_published_today() -> bool:
    ensure_digest_run_table()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    row = cur.execute("""
        SELECT id
        FROM signal_digest_runs
        WHERE digest_date = ?
          AND status = 'published'
        LIMIT 1
    """, (today_key(),)).fetchone()

    conn.close()
    return row is not None


def mark_digest_published(item_count: int):
    ensure_digest_run_table()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM signal_digest_runs WHERE digest_date = ?", (today_key(),))

    cur.execute("""
        INSERT INTO signal_digest_runs (
            digest_date,
            status,
            item_count
        )
        VALUES (?, 'published', ?)
    """, (today_key(), item_count))

    conn.commit()
    conn.close()


def mark_signals_published(signals):
    news_ids = sorted({
        item.get("news_id")
        for item in signals
        if item.get("news_id") is not None
    })

    if not news_ids:
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    placeholders = ",".join(["?"] * len(news_ids))

    cur.execute(f"""
        UPDATE tariff_signals
        SET status = 'published'
        WHERE status = 'new'
          AND news_id IN ({placeholders})
    """, news_ids)

    conn.commit()
    conn.close()

def send_to_max(text: str):
    load_env()

    token = os.getenv("MAX_BOT_TOKEN")
    channel_id = os.getenv("CHANNEL_ID") or os.getenv("MAX_CHANNEL_ID")

    if not token or not channel_id:
        raise RuntimeError("MAX_BOT_TOKEN or CHANNEL_ID/MAX_CHANNEL_ID not found in environment")

    from publisher import send_message

    result = send_message(
        token,
        channel_id,
        text,
        add_helper_button=False,
        full_article_news_id=None,
        add_full_article_button=False,
    )

    print("publisher.send_message result:", result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true", help="Send digest to MAX channel")
    parser.add_argument("--force", action="store_true", help="Publish even if today digest was already sent")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    signals = get_recent_signals(limit=args.limit)
    text = build_digest(signals)

    print(text)

    if args.publish:
        if was_digest_published_today() and not args.force:
            print()
            print("=== already published today; use --force to publish again ===")
            return

        print()
        print("=== publishing to MAX ===")
        send_to_max(text)
        mark_signals_published(signals)
        mark_digest_published(len(signals))
        print("signal digest marked as published")


if __name__ == "__main__":
    main()
