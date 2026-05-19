import re
import os
from typing import Dict, List, Tuple

SCORE_WEIGHTS = {
    'marketplace': 30,
    'regulation': 25,
    'court': 25,
    'fine': 25,
    'seller_impact': 20,
    'deal': 20,
    'bankruptcy': 20,
    'restriction': 15,
    'important_sale': 15,
    'logistics': 10,
    'commission': 10,
    'general': 5
}

# Minimum score threshold - filter out low-quality items
MIN_SCORE_THRESHOLD = int(os.getenv("MIN_SCORE_THRESHOLD", "15"))

# Source priority weights (Tier 1 = highest)
SOURCE_PRIORITY = {
    'tier1': 20,   # Ozon, WB, Yandex direct
    'tier2': 10,   # Retail, Oborot, E-commerce media
    'tier3': 0,    # General news (RBC, CNews, vc.ru)
}

# Source name to tier mapping (matches parsers.py feed names)
SOURCE_TIER_MAP = {
    'Ozon Seller API': 'tier1',
    'Ozon Seller News': 'tier1',
    'WB Docs News': 'tier1',
    'Yandex Market Dev': 'tier1',
    'Retail.ru': 'tier2',
    'Oborot.ru': 'tier2',
    'E-Pepper': 'tier2',
    'Право.ru': 'tier2',
    'МосГорСуд': 'tier2',
    'МособлСуд': 'tier2',
}

PRIORITY_BUCKETS = {
    'critical': ['court', 'fine', 'regulation', 'bankruptcy', 'restriction'],
    'high': ['marketplace', 'seller_impact', 'deal', 'important_sale'],
    'medium': ['commission', 'logistics'],
    'low': ['general']
}

KEYWORD_PATTERNS = {
    'court': ['суд', 'арбитраж', 'иск', 'взыскание', 'решение суда', 'мосгорсуд', 'кадатр', 'спор', 'тяжба'],
    'fine': ['штраф', 'взыскание', 'компенсация', 'убытки', 'неустойка', 'пеня', 'пени'],
    'regulation': ['закон', 'фз', 'фас', 'поправка', 'правило', 'регулирование', 'требование', 'лицензия', 'сертификат'],
    'bankruptcy': ['банкрот', 'ликвидация', 'закрыт', 'убыток', 'долг', 'дефолт'],
    'restriction': ['блокировка', 'бан', 'ограничение', 'приостановка', 'запрет', 'удаление'],
    'marketplace': ['маркетплейс', 'озон', 'wildberries', 'wb', 'яндекс маркет', 'мегамаркет', 'ozon', 'aliexpress'],
    'seller_impact': ['изменение правил', 'повышение тарифа', 'снижение', 'новое правило', 'комиссия'],
    'deal': ['сделка', 'приобретение', 'покупка', 'продажа', 'инвестиция', 'миллиард', 'миллион'],
    'important_sale': ['акция', 'скидка', 'распродажа', 'спецпредложение', 'промокод', 'бонус', 'кешбэк'],
    'logistics': ['логистика', 'доставка', 'склад', 'фулфилмент', 'транспорт'],
    'commission': ['комиссия', 'тариф', 'стоимость', 'цена', '利润']
}

NOISE_PATTERNS = [
    # Events without seller impact
    r'конференция',
    r'выставка',
    r'мероприятие',
    r'презентация',
    r'интервью',
    r'форум',
    r'митап',
    r'вебинар',
    # HR / career noise
    r'назначение',
    r'вакансия',
    r'приём на работу',
    r'карьера',
    r'hr',
    r'сокращение',
    r'увольнение',
    r'найм',
    r'новый глава',
    r'новый директор',
    r'гендиректор',
    # Corporate / strategy
    r'спонсор',
    r'благотворительн',
    r'иммерсивн',
    r'культурн',
    r'спортивн',
    r'миссия',
    r'стратеги',
    r'планы развития',
    # Local facilities (no broad impact)
    r'открытие склада',
    r'новый склад',
    r'новое помещение',
    r'открытие офиса',
    r'новый офис',
    r'зелёный свет',
    # Personal / opinion
    r'мнение',
    r'колонка',
    r'блог',
    r'личный опыт',
    # Real estate (unless massive)
    r'аренда помещен',
    r'купили офис',
    r'продали офис',
    r'арендовали помещен',
    # Routine news without impact
    r'поздравляем',
    r'праздник',
    r'день рождения',
    r'юбилей',
    r'получил преми',
    r'награда',
    r'рейтинг.*компани',
    r'топ.*компани',
    # === NEW: Political / Macro / International noise ===
    r'поддержал.*орбан',
    r'орбан.*поддержал',
    r'сорос',
    r'нато',
    r'евросоюз',
    r'европейск',
    r'сша',
    r'америка',
    r'китай',
    r'германи',
    r'франци',
    r'выборы',
    r'президент',
    r'правительство',
    r'военн',
    r'конфликт',
    r'санкции',
    r'дипломат',
    r'чехи[я]',
    r'серби[я]',
    r'венгри[я]',
    r'польш[а]',
    r'украин',
    r'ближний восток',
    r'инфляция.*рф',
    r'курс.*доллар',
    r'курс.*евро',
    r'ключевая ставк',
    r'центробанк',
    r'ввп.*росси',
    r'безработиц',
    r'отчёт.*год',
    r'выручка.*год',
    r'финансов.*результат',
    r'дивиденд',
    r'акции.*компани',
    r'ipo',
    # Foreign language noise
    r'相关新闻',
    r'ข่าว',
    r'日本',
    r'한국',
    r'BREAKING',
    r'updated:',
]

def calculate_score(title: str, description: str, category: str = 'general', source: str | None = None) -> Tuple[int, str, List[str]]:
    """Рассчитывает score, priority bucket и reason tags для новости"""
    text = f"{title} {description}".lower()
    matched_tags = []
    total_score = 0
    
    for tag, keywords in KEYWORD_PATTERNS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                weight = SCORE_WEIGHTS.get(tag, 5)
                total_score += weight
                matched_tags.append(tag)
                break
    
    # Apply source priority bonus
    if source:
        tier = SOURCE_TIER_MAP.get(source)
        if tier and SOURCE_PRIORITY.get(tier):
            total_score += SOURCE_PRIORITY[tier]
    
    if category == 'sale':
        total_score += SCORE_WEIGHTS.get('important_sale', 15)
        if 'important_sale' not in matched_tags:
            matched_tags.append('important_sale')
    
    if category == 'legal' or category == 'court':
        total_score += SCORE_WEIGHTS.get('court', 25)
        if 'court' not in matched_tags:
            matched_tags.append('court')
    
    priority_bucket = 'low'
    for bucket, tags in PRIORITY_BUCKETS.items():
        if any(t in matched_tags for t in tags):
            priority_bucket = bucket
            break
    
    return total_score, priority_bucket, matched_tags

def is_noise(title: str, description: str) -> bool:
    """Проверяет, является ли новость шумом"""
    text = f"{title} {description}".lower()
    
    for pattern in NOISE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False

def normalize_title(title: str) -> str:
    """Нормализует заголовок - убирает лишнее"""
    title = re.sub(r'\s+', ' ', title)
    title = title.strip()
    
    if len(title) > 200:
        title = title[:197] + '...'
    
    return title

def score_item(item: Dict) -> Dict:
    """Добавляет score, priority_bucket и reason_tags к item"""
    title = item.get('title', '')
    description = item.get('description', item.get('raw_text', ''))
    category = item.get('category', 'general')
    source = item.get('source', '')
    
    score, priority_bucket, reason_tags = calculate_score(title, description, category, source)
    
    item['score'] = score
    item['priority_bucket'] = priority_bucket
    item['reason_tags'] = ','.join(reason_tags) if reason_tags else ''
    
    return item

def score_items(items: List[Dict]) -> List[Dict]:
    """Применяет scoring к списку новостей"""
    scored = []
    
    for item in items:
        if is_noise(item.get('title', ''), item.get('description', '')):
            continue
        
        item = score_item(item)
        
        # Skip items below minimum score threshold
        if item.get('score', 0) < MIN_SCORE_THRESHOLD:
            continue
        
        scored.append(item)
    
    scored.sort(key=lambda x: (x.get('score', 0), x.get('importance', 'normal')), reverse=True)
    
    return scored
