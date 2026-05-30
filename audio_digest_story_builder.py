import html
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from digest_text_cleaner import clean_digest_item_text

DB_PATH = Path("/opt/newsbot_v2/news_queue.db")
OUT_DIR = Path("/opt/newsbot_v2/audio_digest/scripts")


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"https?://\S+", "", value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def voice_text(value: str) -> str:
    value = clean_text(value)

    replacements = {
        "Ozon": "Озон",
        "Wildberries": "Вайлдберриз",
        "WB": "Вайлдберриз",
        "Яндекс.Маркет": "Яндекс Маркет",
        "FBO": "эф-би-о",
        "FBS": "эф-би-эс",
        "DBS": "ди-би-эс",
        "API": "эй-пи-ай",
        "MAX": "Макс",
        "Seller Helper": "СЭллер ХЭлпер",
        "SaluteSpeech": "Салют Спич",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    # Убираем обрывки, которые плохо звучат в TTS.
    value = value.replace("маркетпл...", "маркетплейсов")
    value = value.replace("маркетп...", "маркетплейсов")
    value = value.replace("нар...", "нарушения")
    value = value.replace("мож...", "может")
    value = value.replace("де...", "детали требуют проверки")
    value = value.replace("Д...", "Детали требуют проверки")

    # Фонетическая подсказка для SaluteSpeech: "сэллер" и "хэлпер" через твёрдое Э.
    value = value.replace("селлеров", "сэллеров")
    value = value.replace("селлерам", "сэллерам")
    value = value.replace("селлерами", "сэллерами")
    value = value.replace("селлера", "сэллера")
    value = value.replace("селлеры", "сэллеры")
    value = value.replace("селлер", "сэллер")

    value = value.replace("Селлеров", "Сэллеров")
    value = value.replace("Селлерам", "Сэллерам")
    value = value.replace("Селлерами", "Сэллерами")
    value = value.replace("Селлера", "Сэллера")
    value = value.replace("Селлеры", "Сэллеры")
    value = value.replace("Селлер", "Сэллер")

    value = value.replace("хелпер", "хэлпер")
    value = value.replace("Хелпер", "Хэлпер")

    # Фонетическая подсказка для SaluteSpeech: нужно звучание "плэй", а не мягкое "плей".
    value = value.replace("маркетплейсов", "маркетплэйсов")
    value = value.replace("маркетплейсы", "маркетплэйсы")
    value = value.replace("маркетплейсах", "маркетплэйсах")
    value = value.replace("маркетплейса", "маркетплэйса")
    value = value.replace("маркетплейс", "маркетплэйс")

    value = value.replace("Маркетплейсов", "Маркетплэйсов")
    value = value.replace("Маркетплейсы", "Маркетплэйсы")
    value = value.replace("Маркетплейсах", "Маркетплэйсах")
    value = value.replace("Маркетплейса", "Маркетплэйса")
    value = value.replace("Маркетплейс", "Маркетплэйс")

    value = re.sub(r"\s+", " ", value).strip()
    return value


def pause_short() -> str:
    return "\n\n"


def pause_mid() -> str:
    return "\n\n"


AUDIO_CLOSING_LINE = "Подробная информация, ссылки и выводы для селлеров — в текстовых постах и дайджесте, выходивших в течение дня."
SOFT_AUDIO_JOKES_WITH_NEWS = [
    "На сегодня всё. Маркетплейсы снова удивили — ровно настолько, насколько мы ожидали.",
    "Финал простой: день прошёл, новости записали, маркетплейсы по традиции не скучали.",
    "Итоги зафиксировали, теперь можно спокойно сверить цифры и идти дальше по плану.",
]
SOFT_AUDIO_JOKES_NO_NEWS = [
    "Редкий день, когда можно не хвататься за калькулятор маржи.",
    "Пользуемся моментом: тишина в новостях — это тоже маленький подарок.",
    "Можно выдохнуть. Ненадолго, конечно, мы же всё ещё про маркетплейсы.",
    "Сегодня без громких поворотов. Даже немного подозрительно.",
]

RU_MONTHS_GEN = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def norm(value: str) -> str:
    value = clean_text(value).lower().replace("ё", "е")
    value = re.sub(r"[^a-zа-я0-9\s]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def get(row, *names, default=""):
    for name in names:
        if name in row.keys() and row[name] is not None:
            return row[name]
    return default


def mp_label(mp: str) -> str:
    return {
        "ozon": "Озон",
        "wildberries": "Вайлдберриз",
        "yandex_market": "Яндекс Маркет",
        "multiple": "несколько площадок",
        "unknown": "регуляторика",
        "wb": "Вайлдберриз",
        "yandex": "Яндекс Маркет",
    }.get(mp or "unknown", mp or "не определено")


def table_exists(cur, table: str) -> bool:
    row = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def editorial_title(title: str, raw: str = "", limit=240) -> str:
    title = clean_text(title)
    raw = clean_text(raw)

    title = re.sub(r"^Новости площадок\s*[🔵🟣🟡⚫️]*\s*", "", title, flags=re.I)
    title = title.replace("нар...", "нарушения")
    title = title.replace("мож...", "может")
    title = title.replace("де...", "детали требуют проверки")
    title = title.replace("Д...", "Детали требуют проверки")

    # Если title явно обрезан, пробуем взять начало raw_text.
    if ("..." in title or "…" in title) and raw and len(raw) > len(title):
        first = re.split(r"(?<=[.!?])\s+", raw)[0]
        if len(first) > 30:
            title = first

    title = clean_text(title)
    title = rewrite_for_audio(title)

    # Убираем типовые хвосты из телеграмных обрезков.
    title = re.sub(r"\s+Раньше написать.*$", "", title)
    title = re.sub(r"\s+С октября вступит.*$", "", title)
    title = re.sub(r":\s*маркетплейсов\.?$", ".", title)

    if len(title) > limit:
        title = title[:limit].rstrip(" ,.;:-") + "."

    # build_script сам добавляет точку после заголовка.
    # Поэтому убираем финальные знаки, чтобы не получить "?.", ".." или "!."
    title = re.sub(r"[.!?]+$", "", title).strip()

    return title


def rewrite_for_audio(title: str) -> str:
    t = norm(title)

    if ("армянск" in t and "отгруз" in t) and (("ozon" in t or "озон" in t) and ("wildberries" in t or "вайлдберриз" in t)):
        return "Озон и Вайлдберриз приостановили отгрузки товаров армянских селлеров в Россию."

    if ("рек слот" in t or ("рекомендован" in t and "слот" in t) or ("слот" in t and "пвз" in t)) and ("ozon" in t or "озон" in t):
        return "Озон меняет рекомендованные слоты отгрузки по FBS."

    if ("страх" in t and ("личн" in t or "кабинет" in t or "ozon" in t or "озон" in t)):
        return "Озон продвигает страхование в личном кабинете продавца."

    if "брошенн" in t and "корзин" in t and ("ozon" in t or "озон" in t):
        return "Озон запускает платный инструмент для работы с брошенными корзинами."

    if "фас" in t and ("ozon" in t or "wildberries" in t or "маркетплейс" in t or "выплат" in t):
        return "ФАС выдала предупреждение Озону и Вайлдберриз из-за условий для продавцов."

    if "туркменистан" in t and ("ozon" in t or "озон" in t):
        return "Озон выходит в Туркменистан и с первого мая вводит отдельные тарифы на логистику."

    if "честный знак" in t and ("блокиров" in t or "продаж" in t):
        return "В Госдуме обсуждают быструю блокировку партий товаров через Честный знак."

    if "платформенной экономике" in t:
        return "Готовится закон о платформенной экономике. Для селлеров это риск новых правил и дополнительных расходов."

    return title


def event_key(title: str, source: str = "", marketplace: str = "") -> str:
    t = norm(title)
    s = norm(source)
    mp = marketplace or "unknown"

    if "фас" in t and ("маркетплейс" in t or "ozon" in t or "wildberries" in t or "выплат" in t):
        return "fas_marketplace_conditions"

    if "туркменистан" in t and "ozon" in t and ("тариф" in t or "логистик" in t):
        return "ozon_turkmenistan_logistics_tariffs"

    if "брошенн" in t and "корзин" in t and ("ozon" in t or "озон" in t):
        return "ozon_abandoned_carts_paid_tool"

    if "честный знак" in t and ("блокиров" in t or "продаж" in t):
        return "regulator_honest_sign_blocking"

    if "оферт" in t and ("обнов" in t or "вступит в силу" in t):
        return f"offer_update:{mp}"

    if ("api" in t or "api" in s or "лимит" in t or "метод" in t) and mp:
        return f"api_or_limits:{mp}:{t[:80]}"

    return "title:" + t[:120]


def is_noise(title: str) -> bool:
    t = norm(title)

    noise = [
        "конкурс",
        "розыгрыш",
        "мерч",
        "вебинар",
        "подкаст",
        "подарк",
        "выигрывайте",
        "акция",
        "распродажа",
        "скидк",
        "курьеры вовремя доставляют",
        "на фоне снегопада",
        "график работы",
        "майские праздники",
        "быстрые выплаты от яндекс банка",
    ]

    return any(x in t for x in noise)


def news_score(row):
    title = norm(get(row, "title"))
    text = norm(get(row, "raw_text", "clean_text", "content", "text"))

    score = 0
    score += safe_int(get(row, "seller_relevance_score", default=0))
    score += safe_int(get(row, "actionability_score", default=0))

    strong_words = [
        "фас", "оферта", "тариф", "комисси", "выплат", "логистик",
        "маркировк", "честный знак", "закон", "селлер", "продавц",
        "ozon", "wildberries", "яндекс маркет", "wb",
        "возврат", "штраф", "удержан", "api", "кабинет продавца",
        "брошенн", "корзин", "туркменистан",
    ]

    for word in strong_words:
        if word in title or word in text:
            score += 2

    if is_noise(title):
        score -= 8

    return score


def load_news(limit=3, digest_date=None):
    """
    Загружает новости только за дату текущего аудиодайджеста.

    Старое поведение брало последние 500 опубликованных новостей без фильтра по дате,
    затем сортировало по score. Из-за этого старые сильные темы могли повторяться
    в новых аудиодайджестах. Теперь выпуск не должен собираться из старых новостей.
    """
    digest_date = digest_date or datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if not table_exists(cur, "news"):
        conn.close()
        return []

    rows = cur.execute("""
        SELECT *
        FROM news
        WHERE created_at >= ?
          AND created_at < date(?, '+1 day')
          AND (
                is_published = 1
                OR lower(COALESCE(seller_decision, '')) IN ('publish', 'published')
              )
        ORDER BY id DESC
        LIMIT 300
    """, (digest_date, digest_date)).fetchall()

    conn.close()

    candidates = []

    for row in rows:
        title = clean_text(get(row, "title"))
        raw = clean_text(get(row, "raw_text", "clean_text", "content", "text"))
        source = clean_text(get(row, "source"))

        if not title or len(title) < 12:
            continue

        if is_noise(title):
            continue

        final_title = editorial_title(title, raw)
        key = event_key(final_title, source)

        candidates.append({
            "id": get(row, "id"),
            "title": final_title,
            "source": source,
            "raw": raw,
            "score": news_score(row),
            "event_key": key,
            "topic_key": audio_topic_key(final_title, source),
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)

    result = []
    seen = set()

    for item in candidates:
        event_k = item.get("event_key")
        topic_k = item.get("topic_key")

        if event_k in seen or topic_k in seen:
            continue

        if event_k:
            seen.add(event_k)
        if topic_k:
            seen.add(topic_k)

        result.append(item)
        if len(result) >= limit:
            break

    return result


def signal_score(row):
    level = get(row, "signal_level", default="")
    urgency = get(row, "urgency", default="")
    signal_type = get(row, "signal_type", default="")

    score = 0

    if level == "high":
        score += 5
    elif level == "medium":
        score += 3

    if urgency == "urgent":
        score += 5
    elif urgency == "daily":
        score += 2

    if signal_type in ("regulator", "offer", "tariff", "payouts", "penalties", "marking", "api"):
        score += 3

    return score


def load_signals(limit=2, exclude_keys=None, digest_date=None):
    """
    Загружает сигналы только за дату текущего аудиодайджеста.

    Старое поведение брало последние 400 сигналов без фильтра по detected_at,
    поэтому в аудио могли повторяться старые сигналы: Туркменистан, Честный знак и т.п.
    """
    exclude_keys = exclude_keys or set()
    digest_date = digest_date or datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if not table_exists(cur, "tariff_signals"):
        conn.close()
        return []

    rows = cur.execute("""
        SELECT *
        FROM tariff_signals
        WHERE status IN ('new', 'published', 'urgent_published')
          AND detected_at >= ?
          AND detected_at < date(?, '+1 day')
        ORDER BY id DESC
        LIMIT 300
    """, (digest_date, digest_date)).fetchall()

    conn.close()

    candidates = []

    for row in rows:
        title = clean_text(get(row, "title"))
        source = clean_text(get(row, "source"))
        marketplace = get(row, "marketplace")
        level = get(row, "signal_level", default="")

        if not title or level not in ("high", "medium"):
            continue

        if is_noise(title):
            continue

        final_title = editorial_title(title)
        key = event_key(final_title, source, marketplace)
        topic_key = audio_topic_key(final_title, marketplace)

        if key in exclude_keys or topic_key in exclude_keys:
            continue

        candidates.append({
            "id": get(row, "id"),
            "title": final_title,
            "source": source,
            "marketplace": marketplace,
            "signal_type": get(row, "signal_type"),
            "level": level,
            "score": signal_score(row),
            "event_key": key,
            "topic_key": topic_key,
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)

    result = []
    seen = set()

    for item in candidates:
        event_k = item.get("event_key")
        topic_k = item.get("topic_key")

        if event_k in seen or topic_k in seen:
            continue

        if event_k:
            seen.add(event_k)
        if topic_k:
            seen.add(topic_k)

        result.append(item)
        if len(result) >= limit:
            break

    return result





# AUDIO DIGEST QUALITY PATCH V1
# Убирает дубли между новостями и сигналами, не даёт обрезать фразы посередине,
# заменяет повторяющийся универсальный шаблон на смысловые выводы.

def audio_topic_key(title, source=""):
    t = norm(title)
    s = norm(source)

    # Нормализуем площадки и типовые префиксы.
    replacements = [
        ("wildberries", "вб"),
        ("вайлдберриз", "вб"),
        ("wb", "вб"),
        ("ozon", "озон"),
        ("яндекс маркет", "яндекс"),
        ("tg oborotru", ""),
        ("oborot ru", ""),
        ("tg marketplace biz", ""),
        ("tg crmmarketplace", ""),
        ("tg mpgo ru", ""),
    ]

    for a, b in replacements:
        t = t.replace(a, b)
        s = s.replace(a, b)

    t = re.sub(r"[^0-9a-zа-яё ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    stop = {
        "и", "в", "во", "на", "по", "с", "со", "для", "от", "до",
        "это", "как", "что", "если", "уже", "теперь", "новости",
        "селлер", "селлера", "селлеров", "продавец", "продавцов",
        "маркетплейс", "маркетплейса", "маркетплейсов",
    }

    words = [w for w in t.split() if len(w) > 2 and w not in stop]

    # Берём самые содержательные первые слова. Этого хватает, чтобы схлопнуть:
    # "Спешите забрать зависшие остатки" и
    # "WB: Спешите забрать зависшие остатки..."
    return " ".join(words[:8])


BAD_AUDIO_TAILS_V1 = {
    "ч",
    "вр",
    "регистраци",
    "фиксированны",
    "мож",
}


def has_bad_audio_tail(text):
    s = norm(text)
    if not s:
        return True

    if any(s.endswith(x) for x in [
        " приобретаемые ч",
        " самое вр",
        " завершила регистраци",
        " были п",
        " фиксированны",
        " товар мож",
    ]):
        return True

    words = s.split()
    if not words:
        return True

    last = words[-1].strip(". ,;:!?")
    if last in BAD_AUDIO_TAILS_V1:
        return True

    if re.fullmatch(r"[а-яё]{1,2}", last) and last not in {"рф", "ндс", "пвз", "фз", "цб"}:
        return True

    return False


def safe_audio_text(text, max_chars=220):
    s = clean_text(text)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return ""

    # Сначала пытаемся взять полное предложение.
    if len(s) > max_chars:
        cut = s[:max_chars]
        pos = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
        if pos >= 80:
            s = cut[:pos + 1].strip()
        else:
            # Если точки нет, режем только по пробелу, не посередине слова.
            pos = cut.rfind(" ")
            s = cut[:pos].strip() if pos >= 80 else cut.strip()

    # Убираем хвостовые обрывки.
    for _ in range(4):
        if not has_bad_audio_tail(s):
            break

        # Если есть предыдущее законченное предложение — оставляем его.
        pos = max(s[:-1].rfind("."), s[:-1].rfind("!"), s[:-1].rfind("?"))
        if pos >= 80:
            s = s[:pos + 1].strip()
            break

        # Иначе отрезаем последнее слово.
        parts = s.split()
        if len(parts) <= 6:
            return ""
        s = " ".join(parts[:-1]).strip()

    s = s.strip(" ,;:-—")
    if not s:
        return ""

    if s[-1] not in ".!?":
        s += "."

    return s



def audio_topic_similar(a, b):
    """
    Более жёсткий дедуп для аудио:
    ловит смысловые дубли вроде
    "На маркетплейсах инфляция ниже" и
    "Инфляция на маркетплейсах ниже официальной".
    """
    a = norm(a)
    b = norm(b)

    if not a or not b:
        return False

    wa = set(w for w in a.split() if len(w) > 3)
    wb = set(w for w in b.split() if len(w) > 3)

    if not wa or not wb:
        return False

    overlap = len(wa & wb)
    smaller = min(len(wa), len(wb))

    if smaller and overlap / smaller >= 0.55:
        return True

    # Отдельно ловим короткие редакторские заголовки по ключевым словам.
    pairs = [
        ("инфляц", "маркетплейс"),
        ("возврат", "остатк"),
        ("тариф", "возврат"),
        ("отзыв", "вид"),
        ("рейтинг", "отзыв"),
    ]

    for x, y in pairs:
        if x in a and y in a and x in b and y in b:
            return True

    return False


def audio_seen_topic(title, used_titles):
    for old in used_titles:
        if audio_topic_similar(title, old):
            return True
    return False


def explain_news(item):
    t = norm(item.get("title", ""))

    if "инфляц" in t and "маркетплейс" in t:
        return "Для селлера это сигнал по цене: покупатель видит маркетплейсы как место более мягкого роста цен, поэтому резкое повышение может сильнее ударить по конверсии."
    if ("отзыв" in t or "рейтинг" in t) and ("вид" in t or "склейк" in t or "товар" in t):
        return "Для селлера это влияет на карточки: отзывы и рейтинг могут начать работать точнее по вариантам товара, поэтому слабые виды внутри склейки лучше проверить отдельно."
    if "ндс" in t or "минпромторг" in t or "налог" in t:
        return "Для селлера это будущий налоговый риск: такие изменения заранее закладывают в цену, юнит-экономику и ассортимент."
    if "возврат" in t or "остатк" in t or "зависш" in t:
        return "Для селлера это скорее сигнал по складской дисциплине: важно не затягивать с вывозом, возвратами и лишними удержаниями."
    if "тариф" in t or "комисси" in t:
        return "Здесь главный риск в марже: нужно пересчитать товары с низким запасом прибыли и проверить, какие позиции могут уйти в минус."
    if "ии" in t or "ассистент" in t or "аналитическ" in t:
        return "Практический смысл — быстрее находить слабые места в продажах, но решения по цене и остаткам всё равно нужно проверять цифрами."
    if "фас" in t:
        return "Для селлеров это регуляторный сигнал: площадкам придётся аккуратнее объяснять условия работы, выплаты и удержания."
    if "брошенн" in t and "корзин" in t:
        return "Это может стать новым платным инструментом продвижения, но его нужно считать отдельно от базовой комиссии."
    if "кабинет" in t or "сводк" in t:
        return "Смысл для продавца простой: быстрее увидеть заказы, возвраты и проблемные места в операционке."
    if "честный знак" in t or "маркировк" in t:
        return "Здесь риск уже не маркетинговый, а регуляторный: ошибки в карточках и маркировке могут стать дороже."

    return ""


def explain_signal(item):
    t = norm(item.get("title", ""))
    signal_type = str(item.get("signal_type") or "")

    if signal_type == "tariff" or "тариф" in t or "комисси" in t:
        return "Проверяем как тарифный риск: если источник подтвердится, такие изменения надо учитывать в марже."
    if signal_type in ("returns", "logistics") or "возврат" in t or "логист" in t:
        return "Это операционный риск: стоит проверить возвраты, сроки вывоза, склады и FBS/FBO-процессы."
    if signal_type == "api" or "api" in t or "метод" in t:
        return "Это техническое изменение для интеграций и отчётов: его стоит учитывать тем, кто ведёт автоматизацию кабинета."
    if signal_type in ("payouts", "penalties") or "штраф" in t or "выплат" in t:
        return "Это риск по деньгам: стоит проверить удержания, выплаты и спорные операции."
    if "ндс" in t or "минпромторг" in t:
        return "Это не изменение сегодняшней комиссии, а будущий налоговый риск для расчёта цены."

    return "Сигнал берём в наблюдение, но не считаем его изменением тарифов без официального подтверждения."

# END AUDIO DIGEST QUALITY PATCH V1

def build_script(news_items, signal_items):
    today = datetime.now().strftime("%d.%m.%Y")

    parts = []

    parts.append(f"Инсайдер Селлер. Вечерний дайджест за {today}.")
    parts.append("Коротко и по делу. Что сегодня важно для продавцов маркетплейсов.")

    used_topics = set()
    used_titles = []

    if news_items:
        parts.append(f"{pause_mid()} Начнём с главного.")

        labels = ["Первое", "Второе", "Третье"]
        news_spoken_idx = 0

        for item in news_items:
            raw_title = item.get("title", "")
            _, cleaned_raw = clean_digest_item_text(raw_title, item.get("raw", ""))
            topic_k = item.get("topic_key") or audio_topic_key(raw_title, item.get("source", ""))

            if topic_k in used_topics or audio_seen_topic(raw_title, used_titles):
                continue

            # Если body начинается тем же lead, берём body, чтобы не дублировать заголовок в аудио.
            audio_seed = cleaned_raw or raw_title
            title = safe_audio_text(audio_seed, max_chars=210)
            if not title:
                continue

            used_topics.add(topic_k)
            used_titles.append(raw_title)

            explanation = safe_audio_text(explain_news(item), max_chars=220)
            if not explanation:
                continue

            label = labels[news_spoken_idx] if news_spoken_idx < len(labels) else f"Новость номер {news_spoken_idx + 1}"
            news_spoken_idx += 1

            title = voice_text(title)
            explanation = voice_text(explanation)

            parts.append(f"{label}. {title} {pause_short()} {explanation}")
    else:
        parts.append("Сегодня без сильных новостей, которые стоило бы отдельно выносить в выпуск.")

    clean_signal_items = []
    for item in signal_items or []:
        raw_title = item.get("title", "")
        topic_k = item.get("topic_key") or audio_topic_key(raw_title, item.get("marketplace", ""))

        if topic_k in used_topics or audio_seen_topic(raw_title, used_titles):
            continue

        title = safe_audio_text(raw_title, max_chars=190)
        if not title:
            continue

        used_topics.add(topic_k)
        used_titles.append(raw_title)
        copied = dict(item)
        copied["title"] = title
        clean_signal_items.append(copied)

    if clean_signal_items:
        parts.append(f"{pause_mid()} Теперь коротко о сигналах, которые стоит держать в поле зрения.")

        signal_labels = [
            "Первый сигнал",
            "Второй сигнал",
            "Третий сигнал",
            "Четвёртый сигнал",
            "Пятый сигнал",
        ]

        for idx, item in enumerate(clean_signal_items):
            label = signal_labels[idx] if idx < len(signal_labels) else f"Сигнал номер {idx + 1}"
            mp = voice_text(mp_label(item.get("marketplace")))
            title = voice_text(item["title"])
            meaning = voice_text(safe_audio_text(explain_signal(item), max_chars=210))

            if mp in ("регуляторика", "не определено"):
                parts.append(f"{label}. {title} {pause_short()} {meaning}")
            else:
                parts.append(f"{label}. {mp}. {title} {pause_short()} {meaning}")

        parts.append("Неподтверждённые новостные сигналы не считаем изменением тарифов, пока нет официального источника.")
    else:
        parts.append("По тарифам, офертам и условиям работы новых сильных сигналов для отдельной проверки сегодня не обнаружено.")

    endings = [
        "На сегодня всё. Берегите маржу, спокойствие и здравый смысл.",
        "Дайджест закончен. Спокойного вечера и точных расчётов.",
        "На сегодня всё. Пусть завтра будет меньше сюрпризов в тарифах и больше ясности в цифрах.",
        "На этом всё. Пусть выплаты приходят вовремя, а комиссии не подкрадываются без предупреждения.",
        "Дайджест на сегодня завершён. Завтра снова посмотрим, где маркетплейсы поменяли правила игры.",
        "Финал на сегодня. Держим руку на пульсе, а калькулятор — рядом.",
        "На сегодня всё. Пусть ночь будет спокойной, а личный кабинет — без новых сюрпризов.",
        "Финиш на сегодня. Новости ушли в архив, а селлерская бдительность остаётся включённой.",
        "На сегодня всё. Пусть товары продаются, возвраты не шалят, а отчёты сходятся с первого раза.",
        "Дайджест завершён. Если маркетплейсы ночью что-то поменяют, утром разберёмся без паники.",
        "На этом всё. Пусть склад не спорит с кабинетом, а кабинет — с бухгалтерией.",
        "Финал выпуска. Сегодня рынок снова напомнил: спокойствие селлера начинается с нормальных данных.",
        "На сегодня всё. Пусть реклама не съедает маржу, а логистика не устраивает квест.",
        "Дайджест закрыт. Завтра проверим, что придумали площадки, регуляторы и народная смекалка.",
        "На этом всё. Пусть ваши карточки видят покупатели, а не только алгоритмы.",
        "Финиш. Пусть в отчётах будет порядок, а в новостях — поменьше внезапных поворотов.",
        "На сегодня всё. Маржу бережём, решения принимаем спокойно, новости держим под контролем.",
        "Дайджест завершён. Пусть завтра будет больше продаж и меньше непонятных удержаний.",
        "Финал на сегодня. Выдыхайте: если что-то важное всплывёт, мы это поймаем.",
        "На этом всё. Хорошего вечера и кабинета без красных уведомлений.",
        "Дайджест закрыт. Пусть цифры сходятся, товары двигаются, а правила меняются хотя бы с предупреждением.",
        "На сегодня всё. Увидимся в следующем выпуске — с фактами, без шума и лишней паники.",
        "Финиш выпуска. Пусть маркетплейсы работают, покупатели покупают, а селлеры спят спокойно.",
        "На этом всё. Завтра снова отделим важное от информационного шума.",
    ]
    now = datetime.now()
    ending = endings[(now.toordinal() + now.hour + len(parts)) % len(endings)]
    parts.append(ending)

    return " ".join(parts)


def _parse_digest_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt)
        except Exception:
            pass
    return None


def _resolve_digest_date(items, digest_date=None):
    dt = _parse_digest_date(digest_date)
    if dt:
        return dt
    for item in items or []:
        for key in ("digest_date", "created_at", "published_at", "detected_at"):
            dt = _parse_digest_date(item.get(key))
            if dt:
                return dt
    return None


def _intro_for_digest_date(items, digest_date=None):
    dt = _resolve_digest_date(items, digest_date=digest_date)
    date_text = f"{dt.day} {RU_MONTHS_GEN.get(dt.month, '')}".strip() if dt else "сегодня"
    return f"Коротко по новостям, на которые стоит обратить внимание за {date_text}."


def build_human_audio_digest(items, intro=None, item_min_chars=220, item_max_chars=350, max_items=5, digest_date=None):
    intro_line = intro or _intro_for_digest_date(items, digest_date=digest_date)
    normalized_items = list(items or [])[:max_items]

    parts = [voice_text(clean_text(intro_line))]
    news_paragraphs = []

    for item in normalized_items:
        title = clean_text(item.get("title", ""))
        body = clean_text(item.get("body") or item.get("raw") or item.get("raw_text") or "")
        source = clean_text(item.get("source", ""))
        link = clean_text(item.get("link", ""))

        cleaned_title, cleaned_body = clean_digest_item_text(title, body)
        seed = cleaned_body or cleaned_title
        seed = re.sub(r"\bИсточник\s*:\s*.*$", "", seed, flags=re.IGNORECASE)
        seed = re.sub(r"https?://\S+|t\.me/\S+", "", seed, flags=re.IGNORECASE)
        seed = seed.strip()

        if not seed:
            paragraph = "Площадка сообщила об обновлении, детали лучше смотреть в текстовом посте."
        else:
            why = ""
            if source:
                why = f" Это стоит внимания, потому что новость пришла по линии {source} и может повлиять на рабочие процессы."
            paragraph = f"{seed}{why}"

        paragraph = re.sub(r"\s+", " ", paragraph).strip()
        if len(paragraph) > item_max_chars:
            paragraph = safe_audio_text(paragraph, max_chars=item_max_chars)
        if len(paragraph) < item_min_chars and cleaned_title and cleaned_title.lower() not in paragraph.lower():
            paragraph = f"{paragraph} В двух словах: {cleaned_title}."

        paragraph = paragraph.replace("Источник:", "").replace("Seller Helper", "")
        paragraph = paragraph.replace("Проверить комиссию", "").replace("Рассчитать комиссии", "")
        paragraph = paragraph.replace("Если у вас плохо прогружаются файлы", "")
        paragraph = paragraph.replace("все посты также доступны в MAX", "")
        paragraph = paragraph.replace(link, "") if link else paragraph
        paragraph = re.sub(r"\s+", " ", paragraph).strip()
        paragraph = voice_text(paragraph)
        if paragraph:
            news_paragraphs.append(paragraph)

    parts.extend(news_paragraphs)
    if news_paragraphs:
        parts.append(AUDIO_CLOSING_LINE)
        jokes_pool = SOFT_AUDIO_JOKES_WITH_NEWS
    else:
        parts.append("Значимых новостей на сегодня нет.")
        jokes_pool = SOFT_AUDIO_JOKES_NO_NEWS
    now = datetime.now()
    parts.append(jokes_pool[(now.toordinal() + len(news_paragraphs)) % len(jokes_pool)])
    return "\n\n".join([p for p in parts if p]).strip()


def final_voice_cleanup(value: str) -> str:
    value = value or ""

    # Убираем двойные точки и лишние пробелы перед знаками.
    value = re.sub(r"\.{2,}", ".", value)
    value = re.sub(r"\s+([.,:;!?])", r"\1", value)
    value = re.sub(r"\s+", " ", value).strip()

    # Убираем универсальные служебные вставки из аудиоверсии.
    # audio_digest_style_v1_extra_patterns
    bad_seller_check_patterns = [
        r"Что\s+проверить\s+с[еэ]ллеру[:：]?[^.?!]*(?:[.?!]|$)",
        r"На\s+что\s+обратить\s+внимание\s+с[еэ]ллеру[:：]?[^.?!]*(?:[.?!]|$)",
        r"Проверьте[:：]?\s*[^.?!]*(?:цен[уы]|остатк|выплат|логистик|операционн)[^.?!]*(?:[.?!]|$)",
        r"С[еэ]ллеру\s+стоит\s+проверить[:：]?\s*[^.?!]*(?:[.?!]|$)",
        r"Для\s+с[еэ]ллера\s+это\s+повод\s+проверить[:：]?\s*[^.?!]*(?:[.?!]|$)",
        r"Для\s+с[еэ]ллера\s+это\s+повод\s+проверить,?\s+влияет\s+ли\s+новость\s+на\s+цену,\s+остатки,\s+выплаты\s+или\s+операционные\s+действия\.",
        r"Главный\s+вопрос\s+для\s+с[еэ]ллера\s+[—-]\s+как\s+это\s+повлияет\s+на\s+расходы,\s+выплаты\s+и\s+операционные\s+действия\.",
        r"Проверьте,?\s+влияет\s+ли\s+новость\s+на\s+цену,\s+остатки,\s+выплаты,\s+логистику\s+или\s+операционные\s+действия\s+селлера\.",
    ]
    for pattern in bad_seller_check_patterns:
        value = re.sub(pattern, "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s{2,}", " ", value).strip()

    # Делаем блок сигналов более естественным для голоса.

    # Небольшая речевая правка.
    value = value.replace("Дайджест окончен.", "На сегодня всё.")
    value = value.replace("Если у вас плохо прогружаются файлы", "")
    value = value.replace("все посты также доступны в MAX", "")

    # audio_digest_style_v1_voice_cleanup
    value = value.replace("сЭллерская бдительность", "селлерская бдительность")
    value = value.replace("СЭллерская бдительность", "Селлерская бдительность")
    value = value.replace("сЭллер", "селлер")
    value = value.replace("СЭллер", "Селлер")
    value = re.sub(r"\s+Что сегодня важно для продавцов маркетплэйсов\.", " Коротко о главном для продавцов маркетплейсов.", value)
    value = re.sub(r"Сегодня без сильных новостей, которые стоило бы отдельно выносить в выпуск\.", "Сегодня без новостей, которые требуют отдельного срочного выпуска.", value)
    value = re.sub(r"По тарифам, офертам и условиям работы новых сильных сигналов для отдельной проверки сегодня не обнаружено\.", "По тарифам, офертам и условиям работы новых жёстких сигналов сегодня не было.", value)


    return value



# --- PRODUCTION HOTFIX: clearer audio digest structure v2 ---
# Goal: make TTS script sound like a human digest, not a glued RSS paragraph.
# Rules:
# - title first, body second;
# - no "В двух словах" title suffix;
# - remove title duplication from body;
# - short, separated blocks;
# - explicit seller takeaway when useful.

def _audio_strip_noise_v2(text: str) -> str:
    text = clean_text(text or "")
    text = re.sub(r"https?://\S+|t\.me/\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bИсточник\s*:\s*.*$", "", text, flags=re.IGNORECASE)
    text = text.replace("Seller Helper", "")
    text = text.replace("Проверить комиссию", "")
    text = text.replace("Рассчитать комиссии", "")
    text = text.replace("Если у вас плохо прогружаются файлы", "")
    text = text.replace("все посты также доступны в MAX", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _audio_remove_title_prefix_v2(title: str, body: str) -> str:
    title = _audio_strip_noise_v2(title)
    body = _audio_strip_noise_v2(body)

    if not title or not body:
        return body

    def norm(v: str) -> str:
        return re.sub(r"[^а-яa-z0-9]+", " ", (v or "").lower().replace("ё", "е")).strip()

    # Remove exact textual prefix first.
    for prefix in [title, title.rstrip(".!?"), " ".join(title.split()[:10]), " ".join(title.split()[:8]), " ".join(title.split()[:6])]:
        prefix = prefix.strip()
        if len(prefix) >= 20 and body.lower().replace("ё", "е").startswith(prefix.lower().replace("ё", "е")):
            body = body[len(prefix):].lstrip(" .—-:;")
            break

    # Normalized fallback: if body still starts with title words, cut by words.
    title_words = title.split()
    body_words = body.split()
    for n in range(min(12, len(title_words)), 4, -1):
        if norm(" ".join(body_words[:n])) == norm(" ".join(title_words[:n])):
            body = " ".join(body_words[n:]).lstrip(" .—-:;")
            break

    # Fix common glued case: title ended, body starts immediately with capital word.
    body = re.sub(r"\s+", " ", body).strip()
    return body


def _audio_summary_v2(text: str, max_chars: int = 260) -> str:
    text = _audio_strip_noise_v2(text)
    if not text:
        return ""

    # Drop awkward lead-in fragments that sound bad in voice.
    bad_starts = [
        r"^Но\s+дальше\s+возникает\s+ключевой\s+вопрос[:：]?\s*",
        r"^В\s+двух\s+словах[:：]?\s*",
        r"^Что\s+произошло[:：]?\s*",
        r"^Звучит\s+хорошо\.\s*",
    ]
    for pat in bad_starts:
        text = re.sub(pat, "", text, flags=re.IGNORECASE).strip()

    text = safe_audio_text(text, max_chars=max_chars)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _audio_takeaway_v2(title: str, body: str, source: str = "") -> str:
    joined = f"{title} {body}".lower().replace("ё", "е")

    if re.search(r"штраф|фнс|налог|самозанят|провер|блокиров|приостанов|выплат|оферт|маркиров", joined):
        return "Для селлера это повод проверить, не затрагивает ли новость деньги, документы, выплаты или правила площадки."

    if re.search(r"логистик|склад|поставк|возврат|доставк|сортиров", joined):
        return "Для селлера главный смысл — заранее учитывать возможное влияние на логистику, сроки и операционные расходы."

    if re.search(r"прямых продаж|сайт|трафик|собственн", joined):
        return "Вывод простой: маркетплейсы остаются основным каналом, но запасной канал продаж становится всё полезнее."

    if re.search(r"аналитик|рынок|исследован|статистик|тренд|динамик", joined):
        return "Это скорее рыночный сигнал, чем срочная инструкция, но его стоит держать в голове при планировании."

    return "Главное — не принимать решение по заголовку, а смотреть, влияет ли новость на ваши товары, процессы или маржу."


def _audio_item_label_v2(index: int) -> str:
    labels = {
        1: "Первая новость.",
        2: "Вторая новость.",
        3: "Третья новость.",
        4: "Ещё один сигнал.",
        5: "И коротко ещё.",
    }
    return labels.get(index, "Следующий сигнал.")


def build_human_audio_digest(items, intro=None, item_min_chars=120, item_max_chars=260, max_items=5, digest_date=None):
    intro_line = intro or _intro_for_digest_date(items, digest_date=digest_date)
    normalized_items = list(items or [])[:max_items]

    parts = [
        voice_text(clean_text(intro_line)),
    ]

    news_count = 0

    for idx, item in enumerate(normalized_items, start=1):
        title = _audio_strip_noise_v2(item.get("title", ""))
        body = item.get("body") or item.get("raw") or item.get("raw_text") or ""
        source = _audio_strip_noise_v2(item.get("source", ""))

        cleaned_title, cleaned_body = clean_digest_item_text(title, body)
        title = _audio_strip_noise_v2(cleaned_title or title)
        body = _audio_remove_title_prefix_v2(title, cleaned_body or body)

        if not title and not body:
            continue

        summary = _audio_summary_v2(body, max_chars=item_max_chars)
        takeaway = _audio_takeaway_v2(title, summary, source)

        block_parts = [_audio_item_label_v2(idx)]

        if title:
            # TTS needs a hard sentence boundary between title and body.
            title = re.sub(r"\\s+", " ", title).strip()
            if title and not re.search(r"[.!?]$", title):
                title = title + "."
            block_parts.append(title)

        if summary and summary.lower().replace("ё", "е") not in (title or "").lower().replace("ё", "е"):
            block_parts.append(summary.rstrip(".!?") + ".")

        if takeaway:
            block_parts.append(takeaway)

        paragraph = " ".join(block_parts)
        paragraph = re.sub(r"\bВ\s+двух\s+словах[:：]?\s*", "", paragraph, flags=re.IGNORECASE)
        paragraph = re.sub(r"\s+", " ", paragraph).strip()
        paragraph = voice_text(paragraph)

        if paragraph:
            parts.append(paragraph)
            news_count += 1

    if news_count:
        parts.append("Подробности — в текстовом дайджесте канала.")
        jokes_pool = SOFT_AUDIO_JOKES_WITH_NEWS
    else:
        parts.append("Значимых новостей на сегодня нет. Значит, можно спокойно проверить отчёты и не искать пожар там, где его нет.")
        jokes_pool = SOFT_AUDIO_JOKES_NO_NEWS

    now = datetime.now()
    parts.append(jokes_pool[(now.toordinal() + news_count) % len(jokes_pool)])

    # Double newlines are useful for human reading and usually give TTS a softer break.
    script = "\n\n".join([p for p in parts if p]).strip()
    return script

def save_script(script, news_count, signal_count):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"audio_digest_script_{ts}.txt"
    path.write_text(script, encoding="utf-8")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS audio_digest_scripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        digest_date TEXT,
        script_path TEXT,
        script_text TEXT,
        news_count INTEGER DEFAULT 0,
        signal_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
        INSERT INTO audio_digest_scripts (
            digest_date,
            script_path,
            script_text,
            news_count,
            signal_count
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d"),
        str(path),
        script,
        news_count,
        signal_count,
    ))

    conn.commit()
    conn.close()

    return path


def main():
    news_items = load_news(limit=3)
    exclude_keys = set()
    for item in news_items:
        if item.get("event_key"):
            exclude_keys.add(item["event_key"])
        if item.get("topic_key"):
            exclude_keys.add(item["topic_key"])

    signal_items = load_signals(limit=2, exclude_keys=exclude_keys)

    merged_items = [
        {"title": i.get("title", ""), "body": i.get("raw", ""), "source": i.get("source", ""), "link": ""}
        for i in news_items
    ] + [
        {"title": i.get("title", ""), "body": i.get("title", ""), "source": i.get("source", ""), "link": ""}
        for i in signal_items
    ]

    script = build_human_audio_digest(merged_items)
    script = voice_text(script)
    script = final_voice_cleanup(script)
    path = save_script(script, len(news_items), len(signal_items))

    print("=== AUDIO DIGEST SCRIPT ===")
    print(script)
    print()
    print("news_items:", len(news_items))
    print("signal_items:", len(signal_items))
    print("saved:", path)


if __name__ == "__main__":
    main()
