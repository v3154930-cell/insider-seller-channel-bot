import re
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
    r'конференция',
    r'выставка',
    r'мероприятие',
    r'презентация',
    r'интервью',
    r'назначение',
    r'вакансия',
    r'приём на работу',
    r'карьера',
    r'hr',
    r'спонсор',
    r'благотворительн',
    r'иммерсивн',
    r'культурн',
    r'спортивн',
    r'открытие склада \(новый склад\)',
    r'новый склад',
    r'зелёный свет',
    r'миссия',
    r'стратеги'
]

def calculate_score(title: str, description: str, category: str = 'general') -> Tuple[int, str, List[str]]:
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
    
    score, priority_bucket, reason_tags = calculate_score(title, description, category)
    
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
        scored.append(item)
    
    scored.sort(key=lambda x: (x.get('score', 0), x.get('importance', 'normal')), reverse=True)
    
    return scored
