import re

IMPORTANT_KEYWORDS = [
    "комиссия", "тариф", "логистика", "штраф", "изменение правил",
    "убытки", "взыскание", "защита прав", "суд", "судебн",
    "кейс", "опыт", "история", "масштабирование", "оборот", "миллион",
    "289-ФЗ", "закон о маркетплейсах", "рекламн", "формат",
    "закрыт", "открыт инструмент", "нововведение", "правило",
    "аккаунт", "блокировка", "бан", "площадка", "маркетплейс",
    "ozon", "wildberries", "wb", "яндекс", "мегамаркет"
]

IGNORE_KEYWORDS = [
    "открытие склада", "новый склад", "назначение директора",
    "иммерсивность", "зелёный свет", "благотворительн",
    "спортивн", "культурн", "выставка", "конференция",
    "недвижимость", "hr", "карьера", "приём на работу",
    "вакансия", "событие", "мероприятие", "презентация"
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