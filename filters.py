import re

IMPORTANT_KEYWORDS = [
    # Tier 1 - Marketplace direct impact (highest priority)
    "комиссия", "тариф", "процент", "услуга", "стоимость",
    "логистика", "доставка", "фулфилмент", "склад", "пвз",
    "штраф", "неустойка", "пеня", "пени",
    "изменение правил", "новое правило", "нововведение",
    "блокировка", "бан", "аккаунт", "удаление", "скрытие",
    "арбитраж", "суд", "иск", "взыскание", "убытки",
    "289-ФЗ", "закон о маркетплейсах", "регулирование", "сертификация",
    # Tier 2 - Marketplace brands
    "озон", "ozon", "wildberries", "wb", "яндекс маркет", "мегамаркет",
    "маркетплейс", "aliexpress", "яндекс", "telegram магазин",
    # Tier 3 - Seller operations
    "реклама", "продвижение", "контекст", "таргет",
    "документы", "документация", "отчётность", "налог",
    "карточка", "товар", "ассортимент", "категория",
    "отзыв", "рейтинг", "покупатель", "возврат",
    "api", "интеграция", "техническ", "коллбэк", "вебхук",
    "контент", "фото", "видео", "описание"
]

IGNORE_KEYWORDS = [
    # Local warehouse / facility openings (no broad impact)
    "открытие склада", "новый склад", "новое помещение",
    "открытие пвз", "новый пвз", "пвз открылся",
    "открытие офиса", "новый офис",
    # Corporate routine (no seller impact)
    "назначение директора", "назначение гендиректора",
    "смена руководства", "новый глава",
    "иммерсивность", "зелёный свет", "благотворительн",
    "спонсор", "спонсорство", "меценат",
    # Events without direct seller impact
    "спортивн", "культурн", "выставка", "конференция",
    "форум", "митап", "вебинар", "презентация",
    "мероприятие", "событие", "праздник",
    # HR / career noise
    "hr", "карьера", "приём на работу", "вакансия",
    "найм", "увольнение", "сокращение",
    "миссия", "стратеги", "планы развития",
    # Real estate (unless massive impact)
    "недвижимость", "аренда", "офис продали", "офис купили",
    # Interpersonal / opinion pieces
    "интервью", "мнение", "колонка", "блог",
    "история успеха", "личный опыт",
    # === NEW: Political / Macro / General noise ===
    # Global politics - no seller impact
    "орбан", "сорос", "нато", "евросоюз", "европа",
    "сша ", "америка", "китай", "германия", "франция",
    "политика", "выборы", "президент", "правительство",
    "военн", "конфликт", "санкции", "дипломат",
    # Macro economy without direct seller link
    "инфляция", "курс валют", "доллар", "евро",
    "ключевая ставка", "цб рф", "центробанк",
    "ввп", "безработица", "экономический рост",
    # General corporate news without marketplace impact
    "отчёт за год", "финансовый результат", "выручка",
    "ipo", "акции компании", "дивиденд",
    # International events
    "чехия", "сербия", "венгрия", "польша",
    "ближний восток", "украина", "днр", "лнр",
    "相关新闻", "ข่าว"  # Non-relevant foreign language noise
]

def is_important(text):
    """Проверяет, содержит ли текст важные ключевые слова"""
    text_lower = text.lower()
    
    for keyword in IMPORTANT_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    
    return False

def should_ignore(text):
    """Проверяет, содержит ли текст слова для игнорирования"""
    text_lower = text.lower()
    
    for keyword in IGNORE_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    
    return False

def filter_news(title, description, link):
    """Основная функция фильтрации новостей"""
    combined_text = f"{title} {description}"
    
    if should_ignore(combined_text):
        return False
    
    if not is_important(combined_text):
        return False
    
    return True

def extract_amounts(text):
    """Извлекает суммы из текста"""
    patterns = [
        r'(\d+\s*(?:млн|млрд|тыс|руб|₽))',
        r'(\d{1,3}(?:\s*\d{3})*(?:\s*руб|\s*₽))',
    ]
    
    amounts = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        amounts.extend(matches)
    
    return amounts[:3]

def is_court_case(title, description):
    """Определяет, является ли новость судебным кейсом"""
    court_keywords = ["суд", "иск", "арбитраж", "мосгорсуд", "взыскание", "убытки", "решение суда"]
    text_lower = f"{title} {description}".lower()
    
    return any(keyword in text_lower for keyword in court_keywords)

def is_seller_story(title, description):
    """Определяет, является ли новость историей селлера"""
    story_keywords = ["история", "кейс", "опыт", "рост", "оборот", "миллион", "масштабирование", "успех"]
    text_lower = f"{title} {description}".lower()
    
    return any(keyword in text_lower for keyword in story_keywords)