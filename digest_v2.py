#!/usr/bin/env python3
import os
import sys
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any

import pytz

from db import init_db, _fetch_all, mark_news_in_digest
from publisher_v2 import normalize_channel_id
from publisher_imports import send_message
from digest_text_cleaner import clean_digest_item_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("digest_v2")

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

MARKETPLACES = ["Ozon", "Wildberries", "Яндекс Маркет"]

OFFER_KEYWORDS = [
    "оферта", "оферты", "условия", "регламент", "договор",
    "комиссия", "комиссии", "тариф", "тарифы",
    "логистика", "хранение", "возврат", "возвраты",
    "штраф", "штрафы", "ндс", "налог", "выплаты",
    "пвз", "фбо", "fbo", "фбс", "fbs", "dbs",
    "подписка", "premium", "premium pro",
    "маркировка", "честный знак",
]

BLOCK_KEYWORDS = [
    "porsche", "bugatti", "порше", "бугатти",
    "футбол", "хоккей", "теннис", "биатлон",
    "маск", "openai", "альтман",
    "автоваз", "грибы", "метро",
]


def norm(value: Any) -> str:
    return str(value or "").lower().replace("ё", "е")


def item_text(item: Dict[str, Any]) -> str:
    return " ".join([
        norm(item.get("title")),
        norm(item.get("raw_text")),
        norm(item.get("source")),
        norm(item.get("link")),
    ])


def is_blocked(item: Dict[str, Any]) -> bool:
    text = item_text(item)
    return any(word in text for word in BLOCK_KEYWORDS)


def is_offer_related(item: Dict[str, Any]) -> bool:
    text = item_text(item)
    return any(word in text for word in OFFER_KEYWORDS)


def title_key(title: str) -> str:
    t = norm(title)
    for suffix in [" - обсуждение", " — обсуждение", " обсуждение"]:
        t = t.replace(suffix, "")
    return " ".join(t.split())[:140]



# TEXT DIGEST QUALITY PATCH V1
# Semantic dedup + короткий практический вывод для селлера.

def clean_for_topic(value: Any) -> str:
    t = norm(value)
    t = t.replace("wildberries", "вб")
    t = t.replace("вайлдберриз", "вб")
    t = t.replace("wb", "вб")
    t = t.replace("ozon", "озон")
    t = t.replace("яндекс маркет", "яндекс")
    t = t.replace("oborot ru", "")
    t = t.replace("oborot", "")
    t = t.replace("tg oborotru", "")
    t = t.replace("tg marketplace biz", "")
    t = re.sub(r"[^0-9a-zа-яё ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def digest_topic_key(item: Dict[str, Any]) -> str:
    title = clean_for_topic(item.get("title") or "")
    raw = clean_for_topic(item.get("raw_text") or "")
    text = (title + " " + raw).strip()

    stop = {
        "это", "как", "что", "или", "для", "при", "без", "под", "над",
        "селлер", "селлера", "селлеров", "продавец", "продавцов",
        "маркетплейс", "маркетплейса", "маркетплейсов",
        "новости", "день", "сегодня", "теперь", "уже", "если",
    }

    words = [w for w in text.split() if len(w) > 2 and w not in stop]

    # Специальные ключи для частых дублей.
    joined = " ".join(words)

    if "возврат" in joined and ("тариф" in joined or "логистик" in joined or "остатк" in joined) and "вб" in joined:
        return "вб возврат тариф логистика остатки"

    if "инфляц" in joined and ("вб" in joined or "маркетплейс" in joined):
        return "инфляция маркетплейсы"

    if ("отзыв" in joined or "рейтинг" in joined) and ("вид" in joined or "склейк" in joined) and "озон" in joined:
        return "озон отзывы виды товара"

    if "утилизированн" in joined and "озон" in joined and "пвз" in joined:
        return "озон утилизированные товары пвз"

    if "магнит" in joined and "выйти" in joined and "предел" in joined:
        return "магнит маркет выйти за пределы маркетплейса"

    if "lamoda" in joined and "business" in joined:
        return "lamoda business селлеры"

    return " ".join(words[:10])


def digest_topic_similar(a: str, b: str) -> bool:
    a = clean_for_topic(a)
    b = clean_for_topic(b)

    if not a or not b:
        return False

    wa = set(w for w in a.split() if len(w) > 3)
    wb = set(w for w in b.split() if len(w) > 3)

    if not wa or not wb:
        return False

    overlap = len(wa & wb)
    smaller = min(len(wa), len(wb))

    return smaller > 0 and overlap / smaller >= 0.58


def digest_seen_topic(item: Dict[str, Any], seen_topics: set, seen_titles: list) -> bool:
    key = digest_topic_key(item)

    if key and key in seen_topics:
        return True

    title = item.get("title") or ""

    for old_title in seen_titles:
        if digest_topic_similar(title, old_title):
            return True

    return False


def mark_digest_topic_seen(item: Dict[str, Any], seen_topics: set, seen_titles: list) -> None:
    key = digest_topic_key(item)
    if key:
        seen_topics.add(key)
    if item.get("title"):
        seen_titles.append(item.get("title") or "")


def seller_check_line(item: Dict[str, Any]) -> str:
    text = item_text(item)

    if "минэк" in text and "скидк" in text:
        return "Что проверить: как скидки и акции влияют на фактическую цену, маржу и претензии покупателей."
    if "инфляц" in text and "маркетплейс" in text:
        return "Что проверить: не завышается ли цена сильнее рынка и не проседает ли конверсия."
    if ("отзыв" in text or "рейтинг" in text) and ("склейк" in text or "вид товара" in text or "виды товара" in text):
        return "Что проверить: слабые варианты товара внутри склейки, рейтинг и отзывы по каждому виду."
    if "возврат" in text or "обратн" in text or "остатк" in text:
        return "Что проверить: стоимость возврата, сроки вывоза, зависшие остатки и маржу по низкоприбыльным товарам."
    if "тариф" in text or "комисси" in text:
        return "Что проверить: товары с минимальной маржей и категории, где изменение тарифа может увести продажу в минус."
    if "ндс" in text or "налог" in text or "минпромторг" in text:
        return "Что проверить: будущую налоговую нагрузку, цены и ассортимент с низкой маржинальностью."
    if "пвз" in text:
        return "Что проверить: операции через ПВЗ, возвраты, спорные выдачи и ответственность за товар."
    if "api" in text or "метод" in text or "кабинет" in text or "ассистент" in text:
        return "Что проверить: отчёты, интеграции, остатки и автоматические выгрузки."
    if "маркировк" in text or "честный знак" in text:
        return "Что проверить: карточки, документы, коды маркировки и риск блокировок."

    if "алгоритм" in text and "ozon" in text:
        return "Что проверить: это скорее операционный сигнал Ozon, а не прямое изменение комиссии; в расчётах маржи ничего не менять."
    if "выручк" in text or "прибыл" in text:
        return "Что проверить: сравнить динамику выручки с маржей, расходами на продвижение и оборачиваемостью товара."

    return "Что проверить: есть ли прямое влияние на цену, остатки, выплаты или ежедневные операции; если нет — просто взять в наблюдение."

# END TEXT DIGEST QUALITY PATCH V1

def get_digest_items(hours_back: int = 24, limit: int = 20) -> List[Dict[str, Any]]:
    now = datetime.now(MOSCOW_TZ)
    cutoff = (now - timedelta(hours=hours_back)).strftime("%Y-%m-%d %H:%M:%S")

    rows = _fetch_all("""
        SELECT
            id,
            title,
            raw_text,
            link,
            source,
            seller_decision,
            is_published,
            in_digest,
            score,
            priority_bucket,
            seller_relevance_score,
            actionability_score,
            created_at
        FROM news
        WHERE created_at >= ?
          AND seller_decision IN ('publish', 'digest')
          AND seller_decision != 'drop'
        ORDER BY
            CASE seller_decision
                WHEN 'publish' THEN 1
                WHEN 'digest' THEN 2
                ELSE 3
            END,
            seller_relevance_score DESC,
            actionability_score DESC,
            score DESC,
            id DESC
        LIMIT ?
    """, (cutoff, limit * 5))

    items = []
    seen_titles = set()
    seen_links = set()
    seen_topics = set()
    seen_topic_titles = []

    for row in rows:
        item = {
            "id": row[0],
            "title": row[1],
            "raw_text": row[2],
            "link": row[3],
            "source": row[4],
            "seller_decision": row[5],
            "is_published": row[6],
            "in_digest": row[7],
            "score": row[8],
            "priority_bucket": row[9],
            "seller_relevance_score": row[10],
            "actionability_score": row[11],
            "created_at": row[12],
        }

        if is_blocked(item):
            continue

        # Не пускаем в дайджест обзоры, рекламные вставки и эмоциональные истории,
        # которые не дают селлеру конкретного действия.
        if "is_roundup_or_soft_noise" in globals() and is_roundup_or_soft_noise(item):
            continue

        link = item.get("link") or ""
        key = title_key(item.get("title") or "")

        if link and link in seen_links:
            continue
        if key and key in seen_titles:
            continue
        if digest_seen_topic(item, seen_topics, seen_topic_titles):
            continue

        if link:
            seen_links.add(link)
        if key:
            seen_titles.add(key)

        mark_digest_topic_seen(item, seen_topics, seen_topic_titles)
        items.append(item)

        if len(items) >= limit:
            break

    return items



def clean_digest_title(title: str, raw_text: str = "", limit: int = 78) -> str:
    """
    Чистит заголовок для дайджеста.
    У TG-источников title часто содержит заголовок + начало статьи.
    В дайджесте нужен короткий заголовок без обрывков.
    """
    t = str(title or "").strip()
    raw = str(raw_text or "").strip()

    if not t and raw:
        t = raw

    t = t.replace("\n", " ")
    t = " ".join(t.split())
    t = t.replace("...", "…").strip()

    # Исправляем типовые склейки из TG/RSS.
    glue_fixes = [
        (r"(Business)(Lamoda)", r"\1. \2"),
        (r"(товара)\s+(Ozon|Озон)\s+(проводит|тестирует)", r"\1. \2 \3"),
        (r"(товара)\s+(Wildberries|Вайлдберриз)\s+(сообщил|повысит|запускает)", r"\1. \2 \3"),
        (r"(плейса)\s+(Магнит\s+Маркет\s+предложил)", r"\1. \2"),
    ]
    for pattern, repl in glue_fixes:
        t = re.sub(pattern, repl, t)

    if "…" in t:
        before = t.split("…", 1)[0].strip()
        if len(before) >= 25:
            t = before

    # Маркеры, после которых обычно начинается уже текст статьи, а не заголовок.
    markers = [
        " Мне часто ",
        " За выходные ",
        " У меня ",
        " В этом кейсе ",
        " Первые тестовые ",
        " Даже не ",
        " Как думаете",
        " Товары размещаются ",
        " С 15 апреля ",
        " В Налоговый кодекс ",
        " Коллеги из ",
        " Помогает отслеживать ",
        " Эксперты ",
        " Компания ",
        " Модель ",
        " Схема ",
        " Ранее ",
        " Также ",
        " При этом ",
        " Сейчас ",
        " Первый день ",
        " Да, ",
        " Уже ",
    ]

    for marker in markers:
        pos = t.find(marker)
        if pos >= 28:
            t = t[:pos].strip(" -—:;,.")
            break

    # Повтор начала TG-поста: "Открылся ... Открылся ..."
    words = t.split()
    if len(words) > 10:
        first = words[0].strip("«»\"'.,:;!?").lower()
        if len(first) >= 3:
            for i in range(4, min(len(words), 18)):
                wi = words[i].strip("«»\"'.,:;!?").lower()
                if wi == first:
                    candidate = " ".join(words[:i]).strip(" -—:;,.")
                    if len(candidate) >= 25:
                        t = candidate
                        break

    # Если есть нормальная точка рано — режем по первому предложению.
    for b in [". ", "! ", "? "]:
        pos = t.find(b)
        if 28 <= pos <= limit:
            t = t[:pos + 1].strip()
            break

    if len(t) > limit:
        cut = t[:limit].rstrip()
        last_space = cut.rfind(" ")
        if last_space > 45:
            cut = cut[:last_space]
        t = cut.rstrip(" -—:;,.") + "…"

    return t or "Без заголовка"

def format_item_line(item: Dict[str, Any], idx: int) -> str:
    source = item.get("source") or "Источник"
    title = clean_digest_title(item.get("title") or "", item.get("raw_text") or "")
    _, cleaned_body = clean_digest_item_text(title, item.get("raw_text") or "")
    detail = cleaned_body
    if detail:
        parts = re.split(r"(?<=[.!?])\s+", detail)
        detail = " ".join([p.strip() for p in parts[:2] if p.strip()])
    if len(detail) > 260:
        cut = detail[:260]
        sp = cut.rfind(" ")
        detail = (cut[:sp] if sp > 180 else cut).rstrip(" ,;:-") + "…"
    if not detail:
        detail = seller_check_line(item)
    link = item.get("link") or ""

    line = f"{idx}. <b>{title}</b>"
    line += f"\n   Почему важно: {detail}"
    line += f"\n   Источник: {source}"
    if link:
        line += f"\n   Ссылка: {link}"
    return line




# TEXT DIGEST QUALITY PATCH V2
# Убирает дайджесты-обзоры, рекламные/эмоциональные TG-посты и слабые псевдо-тарифные попадания.

ROUNDUP_NOISE_PATTERNS = [
    "выпуск посвящен основным новостям",
    "основным новостям рынка",
    "новости рынка",
    "дайджест",
    "подборка новостей",
]

SOFT_STORY_PATTERNS = [
    "ухожу с маркетплейса",
    "запрещеннограм",
    "творческий случай потребительского терроризма",
    "уникальный и довольно творческий случай",
    "разбегаются глаза от огромного количества каналов",
    "дублирую ссылку еще раз",
    "whitebird",
    "35 выпуск посвящен",
    "выпуск посвящен",
    "основным новостям рынка",
    "подкаст",
    "эфир",
]

def is_roundup_or_soft_noise(item: Dict[str, Any]) -> bool:
    text = item_text(item)

    if any(p in text for p in ROUNDUP_NOISE_PATTERNS):
        return True

    if any(p in text for p in SOFT_STORY_PATTERNS):
        return True

    return False


def is_hard_offer_related(item: Dict[str, Any]) -> bool:
    """
    Более строгий фильтр для блока условий/тарифов.
    Старый is_offer_related смотрел весь raw_text и из-за этого в тарифный блок
    попадали обзоры, эмоциональные истории и посты, где слово 'возврат' случайно
    встречалось внутри длинного текста.
    """
    if is_roundup_or_soft_noise(item):
        return False

    title = norm(item.get("title"))
    raw = norm(item.get("raw_text"))
    source = norm(item.get("source"))

    title_text = title + " " + source
    full_text = title + " " + raw + " " + source

    hard_title_keywords = [
        "тариф", "тарифы", "комисси", "оферт", "регламент", "договор",
        "выплат", "штраф", "штрафы", "ндс", "налог",
        "возврат", "возвраты", "логистик", "хранени",
        "маркировк", "честный знак", "пвз", "fbo", "fbs", "фбо", "фбс",
        "платный возврат", "низким выкупом",
    ]

    # В тарифный блок пускаем в первую очередь то, где сильный сигнал есть в title.
    if any(k in title_text for k in hard_title_keywords):
        return True

    # Регуляторика/скидки — только если есть явная связка с маркетплейсами/ценами.
    if ("минэк" in full_text or "минэконом" in full_text or "фас" in full_text) and (
        "скидк" in full_text or "цен" in full_text or "маркетплейс" in full_text
    ):
        return True

    # API/кабинет — только официальные или явно операционные.
    if ("api" in title_text or "кабинет" in title_text or "метод" in title_text) and (
        source.startswith("official") or "wildberries" in full_text or "wb" in full_text or "яндекс" in full_text
    ):
        return True

    return False

# END TEXT DIGEST QUALITY PATCH V2

def build_morning_digest() -> str:
    now = datetime.now(MOSCOW_TZ)
    items = get_digest_items(hours_back=12, limit=8)
    offer_items = [item for item in items if is_hard_offer_related(item)]

    offer_ids = {item.get("id") for item in offer_items}
    main_items = [item for item in items if item.get("id") not in offer_ids][:5]

    lines = []
    lines.append("🌅 <b>УТРЕННИЙ ДАЙДЖЕСТ ДЛЯ СЕЛЛЕРОВ</b>")
    lines.append(f"📅 {now.strftime('%d.%m.%Y')}")
    lines.append("")

    lines.append("<b>📌 Главное за ночь</b>")
    lines.append("")

    if main_items:
        for idx, item in enumerate(main_items, start=1):
            lines.append(format_item_line(item, idx))
            lines.append("")
    else:
        lines.append("За ночь новых важных материалов для селлеров не обнаружено.")
        lines.append("")

    lines.append("<b>🔎 Что проверить утром</b>")
    lines.append("")
    lines.append("• уведомления в кабинетах Ozon, Wildberries и Яндекс Маркета;")
    lines.append("• изменения по выплатам, логистике, возвратам, комиссиям и штрафам;")
    lines.append("• спорные операции, потери товаров, удержания и новые обращения покупателей.")
    lines.append("")

    if offer_items:
        lines.append("<b>⚠️ Сигналы по условиям / тарифам / выплатам</b>")
        lines.append("")
        for idx, item in enumerate(offer_items[:3], start=1):
            lines.append(format_item_line(item, idx))
            lines.append("")
    else:
        lines.append("<b>✅ По условиям работы маркетплейсов</b>")
        lines.append("")
        lines.append("За ночь явных изменений условий, тарифов, выплат или оферт в базе v2 не обнаружено.")
        lines.append("Проверяемые направления: Ozon, Wildberries, Яндекс Маркет.")
        lines.append("")

    lines.append("---")
    lines.append(f"📊 Релевантных материалов за ночь: {len(items)}")
    lines.append(f"📊 Сигналов по условиям/тарифам/выплатам/офертам: {len(offer_items)}")

    return "\n".join(lines).strip()

def build_evening_digest() -> str:
    now = datetime.now(MOSCOW_TZ)
    items = get_digest_items(hours_back=24, limit=12)
    offer_items = [item for item in items if is_hard_offer_related(item)]
    offer_ids_for_split = {item.get("id") for item in offer_items}
    other_items = [
        item for item in items
        if item.get("id") not in offer_ids_for_split
        and not is_roundup_or_soft_noise(item)
    ]

    lines = []
    lines.append("🌙 <b>ВЕЧЕРНИЙ ДАЙДЖЕСТ ДЛЯ СЕЛЛЕРОВ</b>")
    lines.append(f"📅 {now.strftime('%d.%m.%Y')}")
    lines.append("")

    lines.append("<b>📌 Условия, тарифы, выплаты и оферты</b>")
    lines.append("")

    if offer_items:
        for idx, item in enumerate(offer_items[:7], start=1):
            lines.append(format_item_line(item, idx))
            lines.append("")
    else:
        lines.append("За день явных изменений условий работы маркетплейсов в базе v2 не обнаружено.")
        lines.append("Проверяемые направления: Ozon, Wildberries, Яндекс Маркет.")
        lines.append("")

    if other_items:
        lines.append("<b>📰 Другие важные новости для селлеров</b>")
        lines.append("")
        start_idx = len(offer_items[:7]) + 1
        for idx, item in enumerate(other_items[:5], start=start_idx):
            lines.append(format_item_line(item, idx))
            lines.append("")

    lines.append("---")
    lines.append(f"📊 Всего релевантных материалов за день: {len(items)}")
    lines.append(f"📊 Из них про условия/тарифы/выплаты/оферты: {len(offer_items)}")

    return "\n".join(lines).strip()


def build_digest(mode: str = "evening") -> str:
    if mode == "morning":
        return build_morning_digest()
    return build_evening_digest()


def send_digest(mode: str) -> None:
    token = os.getenv("MAX_BOT_TOKEN")
    channel_id = normalize_channel_id(os.getenv("CHANNEL_ID"))

    if not token:
        raise SystemExit("MAX_BOT_TOKEN is empty")
    if not channel_id:
        raise SystemExit("CHANNEL_ID is empty")

    text = build_digest(mode)

    ok = send_message(token, channel_id, text)
    if not ok:
        raise SystemExit("Digest send failed")

    ids = [item["id"] for item in get_digest_items(24 if mode != "morning" else 12, limit=12)]
    if ids:
        mark_news_in_digest(ids)

    logger.info("Digest sent. mode=%s items=%s", mode, len(ids))


def main():
    init_db()

    mode = "evening"
    should_send = False

    args = sys.argv[1:]
    for arg in args:
        if arg in ["morning", "evening", "final"]:
            mode = "evening" if arg == "final" else arg
        if arg == "--send":
            should_send = True

    if should_send:
        send_digest(mode)
    else:
        print(build_digest(mode))


if __name__ == "__main__":
    main()
