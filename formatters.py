import re
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

def format_news(item):
    """Форматирует новость — HTML для MAX"""
    source = item.get('source', 'Новость')
    news_type = item.get('type', 'general')
    
    emoji_map = {
        'ozon': '📦',
        'wildberries': '🟣',
        'yandex': '🟡',
        'court': '⚖️',
        'seller_story': '💡',
        'general': '📰'
    }
    
    source_emoji = emoji_map.get(news_type, '📰')
    topic_emoji = get_topic_emoji(item['title'], item.get('description', ''))
    hashtags = get_hashtags(item['title'], item.get('description', ''), source)
    
    title = item.get('title', '')
    description = item.get('description', '')
    short_text = item.get('short_text', '') or get_summary(description)
    link = item.get('link', '')
    insight = get_insight(title, description)
    
    post = f"""{source_emoji} <b>{source}</b> {topic_emoji}

<b>{title}</b>

{short_text}

💡 <b>Суть:</b> {insight}

🔗 <a href="{link}">Подробнее</a>

{hashtags}"""
    
    return post
