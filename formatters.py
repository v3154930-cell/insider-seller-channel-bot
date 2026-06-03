import re
import html
from filters import extract_amounts

def get_topic_emoji(title, description):
    """Определяет эмодзи по теме"""
    text = f"{title} {description}".lower()
    if any(w in text for w in ['комисс', 'тариф', 'процент', 'налог']):
        return "💰"
    elif any(w in text for w in ['логистик', 'доставк', 'склад']):
        return "🚚"
    elif any(w in text for w in ['штраф', 'блокировк']):
        return "⚠️"
    elif any(w in text for w in ['закон', 'фз', 'фас']):
        return "⚖️"
    elif any(w in text for w in ['кейс', 'история', 'успех']):
        return "💡"
    else:
        return "📦"

def get_hashtags(title, description, source):
    """Генерирует хештеги"""
    text = f"{title} {description}".lower()
    tags = []
    
    if 'озон' in text or 'ozon' in text:
        tags.extend(['озон', 'ozon', 'маркетплейсы'])
    elif 'wildberries' in text or 'wb' in text:
        tags.extend(['wildberries', 'вилдберриз', 'маркетплейсы'])
    elif 'яндекс' in text:
        tags.extend(['яндекс', 'маркетплейсы'])
    else:
        tags.append('маркетплейсы')
    
    if any(w in text for w in ['комиссия', 'тариф']):
        tags.append('комиссии')
    if any(w in text for w in ['логистика', 'доставка']):
        tags.append('логистика')
    if any(w in text for w in ['суд', 'арбитраж']):
        tags.append('арбитраж')
    
    return ' '.join(['#' + t for t in tags[:3]])

def get_summary(text, limit=200):
    """Создаёт краткий пересказ"""
    if not text:
        return ''
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    if len(clean) > limit:
        return clean[:limit-3] + '...'
    return clean


# SELLER MEANING V2
# Fallback для одиночных публикаций, если LLM-enhance не сработал.
# seller_decision остаётся техническим маршрутом publish/digest/drop,
# а смысл для селлера формируется отдельно по теме новости.

def _fmt_norm(value):
    return str(value or "").lower().replace("ё", "е")


def _fmt_clean_spaces(value):
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    value = html.unescape(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def clean_post_title(title, body=""):
    t = _fmt_clean_spaces(title)
    b = _fmt_clean_spaces(body)

    if not t and b:
        t = b

    full = _fmt_norm(f"{t} {b}")

    # Редакторские заголовки для типовых сюжетов.
    if "ухожу с маркетплейса" in full or "запрещеннограм" in full:
        return "Селлеры ищут другие каналы, когда экономика маркетплейса не сходится"

    if "авито" in full and "платн" in full and "возврат" in full:
        return "Авито вводит платный возврат для покупателей с низким выкупом"

    if "озон" in full and ("отзыв" in full or "рейтинг" in full) and ("вид товара" in full or "склейк" in full):
        return "Ozon тестирует раздельные отзывы по видам товара"

    if ("wildberries" in full or "wb" in full or "вайлдберриз" in full) and "возврат" in full and "21 мая" in full:
        return "Wildberries повышает тарифы на возврат товаров со складов"

    # Типовые склейки из TG/RSS.
    fixes = [
        (r"(Business)(Lamoda)", r"\1. \2"),
        (r"(товара)\s+(Ozon|Озон)\s+(проводит|тестирует)", r"\1. \2 \3"),
        (r"(товара)\s+(Wildberries|Вайлдберриз)\s+(сообщил|повысит|запускает)", r"\1. \2 \3"),
        (r"(сайте)\s+(WB|Wildberries|Вайлдберриз)\s+(сообщил|запустил)", r"\1. \2 \3"),
    ]

    for pattern, repl in fixes:
        t = re.sub(pattern, repl, t)

    # Если заголовок содержит заголовок + начало текста, режем по первому нормальному предложению.
    for sep in [". ", "! ", "? "]:
        pos = t.find(sep)
        if 35 <= pos <= 115:
            t = t[:pos + 1].strip()
            break

    if len(t) > 115:
        cut = t[:115].rstrip()
        pos = cut.rfind(" ")
        if pos > 65:
            cut = cut[:pos]
        t = cut.rstrip(" ,;:-—") + "…"

    return t or "Новость для селлеров"


def _drop_broken_start(text):
    """
    Убирает начало, если текст стартует с хвоста слова после неудачного удаления заголовка:
    'бликовать.', 'лейке.', 'ие полгода.', 'это сделать сейчас.'
    """
    s = _fmt_clean_spaces(text)

    bad_starts = [
        "бликовать.",
        "лейке.",
        "это сделать сейчас.",
        "ие полгода",
        "это сделать сейчас",
    ]

    low = _fmt_norm(s)
    for bad in bad_starts:
        if low.startswith(bad):
            pos = max(s.find(". "), s.find("! "), s.find("? "))
            if pos >= 0:
                return s[pos + 2:].strip()

    return s


def _remove_title_overlap(title, body):
    """
    Убирает из body только аккуратный повтор короткого заголовка.
    Не режет по длине длинного title из БД, потому что там часто title + начало статьи.
    """
    body_clean = _fmt_clean_spaces(body)
    clean_title = clean_post_title(title, body)
    title_plain = _fmt_clean_spaces(clean_title).rstrip("…").strip(" .!?:;—-")

    if not body_clean or not title_plain:
        return body_clean

    body_low = _fmt_norm(body_clean)
    title_low = _fmt_norm(title_plain)

    # Если body начинается с короткого заголовка — убираем только его.
    if len(title_low) >= 25 and body_low.startswith(title_low):
        rest = body_clean[len(title_plain):].strip(" .—:-")
        if len(rest) >= 80:
            return rest

    # Частый случай: заголовок содержит "Тема + Тема подробнее".
    # Тогда убираем первое предложение/первый повтор, но только по границе.
    first_sentence_end = min(
        [p for p in [
            body_clean.find(". "),
            body_clean.find("! "),
            body_clean.find("? "),
        ] if p >= 25] or [-1]
    )

    if first_sentence_end >= 25:
        first_sentence = body_clean[:first_sentence_end + 1]
        if _fmt_norm(first_sentence).startswith(title_low[:30]):
            rest = body_clean[first_sentence_end + 2:].strip()
            if len(rest) >= 80:
                return rest

    return body_clean


def safe_post_summary(title, body, limit=420):
    body_clean = _remove_title_overlap(title, body)
    body_clean = _drop_broken_start(body_clean)
    body_clean = re.sub(r"\s+", " ", body_clean).strip()

    if not body_clean:
        return ""

    if len(body_clean) <= limit:
        return body_clean

    cut = body_clean[:limit].rstrip()

    # Режем только по границе предложения, если можем.
    pos = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if pos >= 160:
        return cut[:pos + 1].strip()

    # Иначе по пробелу, но не посередине слова.
    pos = cut.rfind(" ")
    if pos >= 160:
        return cut[:pos].rstrip(" ,;:-—") + "…"

    return cut.rstrip(" ,;:-—") + "…"


def seller_meaning_by_topic(title, body="", source=""):
    """
    Safe seller meaning generator.

    Правила:
    - не вырезает случайные куски из body;
    - не берёт хвосты слов;
    - сначала ловит точные бизнес-сценарии;
    - всегда возвращает законченную прикладную фразу для селлера.
    """
    title = title or ""
    body = body or ""
    source = source or ""

    raw = f"{title} {body} {source}"
    low = raw.lower().replace("ё", "е")

    def has_any(*words):
        return any(w.lower().replace("ё", "е") in low for w in words)

    def has_all(*words):
        return all(w.lower().replace("ё", "е") in low for w in words)

    # WB: возврат товаров со складов / зависшие остатки / рост тарифа
    if (
        has_any("wildberries", "wb", "вайлдберриз")
        and has_any("возврат товаров", "возврат товара", "вернуть товар", "возврат со склад", "со складов")
        and has_any("тариф", "повышает", "стоимость", "дороже", "65 рублей", "85 рублей", "остатк")
    ):
        return "Проверьте зависшие остатки на складах WB: часть товаров выгоднее вывести до повышения тарифа, иначе возврат станет дороже."

    # Уход с маркетплейсов / альтернативные каналы / экономика не сходится
    if has_any(
        "ухожу с маркетплейса",
        "уходят с маркетплейса",
        "сворачивают продажи",
        "ищут другие варианты",
        "другие каналы",
        "альтернативные каналы",
        "вернуть хоть часть вложенного",
        "по нормальным ценам",
        "запрещеннограм"
    ):
        return "Если экономика на маркетплейсе не сходится, проверьте маржинальность, рекламные расходы и альтернативные каналы продаж до полного ухода с площадки."

    # Авито / платный возврат / низкий выкуп
    if (
        has_any("авито", "авито доставка")
        and has_any("платный возврат", "низким выкупом", "процент выкупа", "не забирает")
    ):
        return "Проверьте, как платный возврат для покупателей с низким выкупом может снизить пустые отправки и улучшить экономику доставки."

    # Отзывы / рейтинг / карточки / склейки
    if has_any("отзыв", "рейтинг", "склейк", "вид товара") or has_all("карточк", "вариант"):
        return "Проверьте карточки и варианты товара: слабые позиции могут отдельно тянуть вниз конверсию и рейтинг."

    # Комиссии / тарифы / оферты / ставки / ИП
    if has_any("комисс", "тариф", "оферт", "ставк", "ип", "индивидуальн", "вознагражден"):
        return "Пересчитайте маржу по затронутым категориям и заранее проверьте товары, где новая ставка съедает прибыль."

    # Общие возвраты / выкуп / доставка
    if has_any("возврат", "выкуп", "не забирает", "доставка"):
        return "Проверьте, как новая логика влияет на выкуп, спорные возвраты и экономику доставки."

    # Цены / инфляция / выручка / спрос
    if has_any("инфляц", "цены", "стоимость", "выручк", "оборот", "спрос", "продаж"):
        return "Проверьте ценовую стратегию: покупатель чувствителен к резкому росту цены, особенно в конкурентных категориях."

    # Реклама / продвижение / ставки
    if has_any("реклам", "продвижен", "cpm", "аукцион", "трафик"):
        return "Проверьте рекламные кампании и ставки: рост стоимости продвижения быстро снижает итоговую прибыль."

    # Логистика / склады / хранение
    if has_any("логист", "склад", "хранен", "фулфилмент", "сортиров"):
        return "Проверьте логистику, хранение и сроки поставки: изменения могут повлиять на себестоимость и доступность товара."

    # Маркировка / документы / регуляторика
    if has_any("маркировк", "честный знак", "документ", "штраф", "правил", "регулирован", "закон"):
        return "Проверьте документы и процессы заранее: регуляторные изменения лучше закрывать до штрафов и блокировок."

    # Финансы / выплаты / платежи
    if has_any("выплат", "платеж", "эквайринг", "банк", "налог", "ндс", "финанс"):
        return "Проверьте денежный поток и удержания: даже небольшие изменения могут повлиять на кассовый разрыв и чистую прибыль."

    # Подарки / сезонный спрос / подборки
    if has_any("подарк", "выбор подарков", "главной средой выбора", "93% россиян"):
        return "Проверьте подарочные наборы, сезонные подборки и упаковку: маркетплейсы становятся главным местом выбора подарков, а значит важны готовые решения и быстрая доставка."

    # Подмены товара / мошеннические возвраты
    if has_any("подменить оригиналы", "подменить оригинал", "копии вещей", "сшить копии", "подмена", "вернуть оригинал", "подменяют товар"):
        return "Усильте контроль возвратов: фотофиксация, пломбы, комплектация и признаки подмены помогают снизить потери на мошеннических возвратах."

    # Рост отдельного маркетплейса / новые каналы продаж
    if has_any("м.видео", "мвидео", "вырос в 5 раз", "маркетплейс вырос"):
        return "Следите за ростом новых площадок: если ваша категория подходит под ассортимент маркетплейса, стоит сравнить комиссии, спрос и условия входа."

    # Частые онлайн-заказы / рост привычки покупать онлайн
    if has_any("каждый третий россиянин", "онлайн-заказы несколько раз в неделю", "делает онлайн-заказы", "несколько раз в неделю"):
        return "Проверьте товары для повторных покупок: частые онлайн-заказы усиливают спрос на расходники, наборы, быструю доставку и понятную цену."

    # ПВЗ / пункты выдачи / сеть выдачи
    if has_any("пвз", "пункт выдачи", "пункты выдачи", "сеть пвз", "за стойкой"):
        return "Проверьте географию доставки и качество упаковки: расширение ПВЗ повышает доступность товара, но ошибки на выдаче и возвратах напрямую влияют на выкуп."

    # Сертификаты происхождения / Армения / документы поставщика
    if has_any("сертификат происхождения", "подтверждать происхождение", "продавцов из армении", "происхождение товаров", "страна происхождения"):
        return "Проверьте документы поставщика и происхождение товара заранее: без подтверждения часть ассортимента может попасть под ограничения или задержки."

    # Юридическая база e-com / договоры / перевозки / закупки
    if has_any("e-com база", "закупками", "перевозками", "договор", "претенз", "правовая база", "юридическая база"):
        return "Проверьте договоры, поставки, перевозку и претензионный порядок: юридические мелочи в e-com быстро превращаются в деньги, штрафы и споры."

    # Невостребованные / забытые товары / магазины возвратов
    if has_any("забытые товары", "забытыми", "невостребованные товары", "магазин товаров с маркетплейсов", "чужие покупки"):
        return "Проверьте потери на невостребованных товарах и возвратной логистике: такие истории показывают, где селлер теряет деньги после невыкупа."


    return ""



def get_insight(title, description):
    """Извлекает главный вывод"""
    text = f"{title} {description}"
    
    amounts = extract_amounts(text)
    if amounts:
        return f"Взыскано: {amounts[0]}"
    
    text_lower = text.lower()
    if 'повыш' in text_lower or 'увели' in text_lower:
        return 'Важное изменение для продавцов'
    elif 'сниз' in text_lower or 'уменьш' in text_lower:
        return 'Положительное изменение'
    elif 'блокир' in text_lower or 'бан' in text_lower:
        return 'Риск для аккаунта'
    elif 'штраф' in text_lower:
        return 'Штрафные санкции'
    elif 'нов' in text_lower or 'запуст' in text_lower:
        return 'Новая возможность'
    else:
        return 'Важная информация для селлеров'


def _traffic_light_for_item(item):
    try:
        rel = int(item.get("seller_relevance_score") or 0)
    except Exception:
        rel = 0
    try:
        act = int(item.get("actionability_score") or 0)
    except Exception:
        act = 0
    try:
        score = int(item.get("score") or 0)
    except Exception:
        score = 0

    best = max(rel, act, score // 10 if score > 10 else score)

    if best >= 7:
        return "🔴"
    if best >= 3:
        return "🟡"
    return "🔵"


def _split_llm_processed_text(body):
    s = _fmt_clean_spaces(body)
    if not s:
        return "", ""
    if not (s.startswith("Кратко:") or "Вывод для селлера:" in s):
        return "", ""
    summary = ""
    meaning = ""
    if "Вывод для селлера:" in s:
        left, right = s.split("Вывод для селлера:", 1)
        summary = left.strip()
        meaning = right.strip()
    else:
        summary = s.strip()
    if summary.startswith("Кратко:"):
        summary = summary[len("Кратко:"):].strip()
    return summary, meaning

def format_news(item, enhanced_text=None):
    """Форматирует новость — HTML для MAX. Fallback без LLM."""
    source = item.get('source', 'Новость')
    title = item.get('title', '') or ''
    traffic_light = _traffic_light_for_item(item)
    body = (
        item.get('processed_text')
        or item.get('short_text')
        or item.get('raw_text')
        or item.get('description')
        or ''
    )

    clean_title = clean_post_title(title, body)
    llm_summary, llm_meaning = _split_llm_processed_text(body)

    if enhanced_text:
        short_text = _fmt_clean_spaces(enhanced_text)
    elif llm_summary:
        short_text = llm_summary
    else:
        short_text = safe_post_summary(title, body, limit=430)

    meaning = llm_meaning or seller_meaning_by_topic(title, body, source)

    # Ссылку НЕ добавляем здесь: publisher_v2 потом вызывает append_source_line().
    post = f"""<b>{traffic_light} 📦 {source}</b>

<b>{clean_title}</b>

{short_text}

<b>🎯 Что это значит для селлера:</b> {meaning}"""

    return post.strip()


def get_item_url(item):
    """Get news URL with fallback."""
    return item.get("url") or item.get("link") or ""


def detect_link_type(item) -> str:
    """Classify URL type: official, forum, or media."""
    url = get_item_url(item)
    if not url:
        return "media"
    url_lower = url.lower()
    official_domains = ['seller.ozon', 'portal.wildberries', 'business.ozon']
    forum_domains = ['telega.in', 'teletype.in', 'forum.seller']
    if any(d in url_lower for d in official_domains):
        return "official"
    if any(d in url_lower for d in forum_domains):
        return "forum"
    return "media"


def get_source_link(item) -> tuple:
    """Get best source link with type."""
    link = item.get("url") or item.get("link") or ""
    link_type = detect_link_type(item)
    return link, link_type


def filter_non_forum_links(items):
    """Filter non-forum links - basic implementation."""
    return items
