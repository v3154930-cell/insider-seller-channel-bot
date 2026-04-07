import re
from filters import extract_amounts

THEME_EMOJI = {
    'комиссия': '💰',
    'тариф': '💰',
    'логистика': '🚚',
    'доставка': '🚚',
    'закон': '⚖️',
    '289-ФЗ': '⚖️',
    'штраф': '⚠️',
    'блокировка': '🚫',
    'бан': '🚫',
    'арбитраж': '⚖️',
    'суд': '⚖️',
    'кейс': '💡',
    'опыт': '💡',
    'история': '💡',
    'оборот': '📈',
    'миллион': '💰',
    'рост': '📈',
    'маркетплейс': '🏪',
    'реклама': '📣',
    'инструмент': '🔧',
    'нововведение': '✨',
    'изменение': '📝',
}

HASHTAGS = {
    'ozon': '#озон #маркетплейсы #ozon',
    'wildberries': '#wildberries #вилдберриз #маркетплейсы',
    'yandex': '#яндекс #маркетплейсы',
    'court': '#арбитраж #суд #юридические',
    'seller_story': '#историяуспеха #опыт #кейс',
}

def get_theme_emoji(title, description):
    """Получает эмодзи по ключевым словам"""
    text = f"{title} {description}".lower()
    for keyword, emoji in THEME_EMOJI.items():
        if keyword in text:
            return emoji
    return '📰'

def get_hashtags(news_type, title, description):
    """Генерирует хештеги на основе типа и содержимого"""
    text = f"{title} {description}".lower()
    tags = []
    
    if 'озон' in text or 'ozon' in text:
        tags.extend(['#озон', '#ozon', '#маркетплейсы'])
    elif 'wildberries' in text or 'wb' in text:
        tags.extend(['#wildberries', '#вилдберриз', '#маркетплейсы'])
    elif 'яндекс' in text:
        tags.extend(['#яндекс', '#маркетплейсы'])
    else:
        tags.append('#маркетплейсы')
    
    if any(w in text for w in ['комиссия', 'тариф', 'цена']):
        tags.append('#комиссии')
    if any(w in text for w in ['логистика', 'доставка']):
        tags.append('#логистика')
    if any(w in text for w in ['суд', 'арбитраж', 'иск']):
        tags.append('#арбитраж')
    if any(w in text for w in ['кейс', 'опыт', 'история']):
        tags.append('#опыт')
    
    return ' '.join(tags[:3])

def get_summary(title, description):
    """Создаёт краткий пересказ"""
    if not description:
        return title[:150]
    
    text = description.strip()
    if len(text) > 180:
        text = text[:177] + '...'
    return text

def get_key_insight(title, description):
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

def format_marketplace_news(item):
    """Форматирует новость маркетплейса"""
    source = item.get('source', 'Новость')
    news_type = item.get('type', 'general')
    
    emoji_map = {
        'ozon': '📦',
        'wildberries': '🏷️',
        'yandex': '🛒',
        'general': '📰'
    }
    
    source_emoji = emoji_map.get(news_type, '📰')
    theme_emoji = get_theme_emoji(item['title'], item.get('description', ''))
    hashtags = get_hashtags(news_type, item['title'], item.get('description', ''))
    
    title = item['title']
    description = item.get('description', '')
    link = item.get('link', '')
    
    summary = get_summary(title, description)
    insight = get_key_insight(title, description)
    
    message = f"""┌─────────────────────────────────────┐
│ {source_emoji} **{source}**                      │
│ {theme_emoji} Обновление                   │
├─────────────────────────────────────┤
│                                      │
│ **{title}**                      │
│                                      │
│ {summary}│                                      │
│ ─────────────────────────────────── │
│ 💡 Суть: {insight}                    │
│                                      │
│ 🔗 [Подробнее]({link})                  │
│                                      │
│ {hashtags}
└─────────────────────────────────────┘"""
    
    return message

def format_court_case(item):
    """Форматирует судебный кейс"""
    title = item['title']
    description = item.get('description', '')
    link = item.get('link', '')
    source = item.get('source', 'Суд')
    
    amounts = extract_amounts(f"{title} {description}")
    amount_str = amounts[0] if amounts else 'не указана'
    
    summary = get_summary(title, description)
    insight = get_key_insight(title, description)
    hashtags = '#арбитраж #суд #юридические #кейс'
    
    message = f"""┌─────────────────────────────────────┐
│ ⚖️ **АРБИТРАЖ**                           │
│ ⚖️ Судебный кейс                    │
├─────────────────────────────────────┤
│                                      │
│ **{title}**                      │
│                                      │
│ {summary}│                                      │
│ ─────────────────────────────────── │
│ 📊 Взыскано: {amount_str}                   │
│                                      │
│ 💡 Вывод: {description[:100] if description else insight}│                                      │
│                                      │
│ 🔗 [Подробнее]({link})                  │
│                                      │
│ {hashtags}
└─────────────────────────────────────┘"""
    
    return message

def format_seller_story(item):
    """Форматирует историю селлера"""
    title = item['title']
    description = item.get('description', '')
    link = item.get('link', '')
    source = item.get('source', 'История')
    
    amounts = extract_amounts(f"{title} {description}")
    summary = get_summary(title, description)
    insight = get_key_insight(title, description)
    hashtags = '#историяуспеха #опыт #кейс #селлер'
    
    message = f"""┌─────────────────────────────────────┐
│ 💡 **ОПЫТ СЕЛЛЕРОВ**                       │
│ 💡 Кейс успеха                      │
├─────────────────────────────────────┤
│                                      │
│ **{title}**                      │
│                                      │
│ {summary}│                                      │
│ ─────────────────────────────────── │
│ 📊 Результат: {amounts[0] if amounts else 'см. в статье'}                    │
│                                      │
│ 💡 Урок: {insight}                    │
│                                      │
│ 🔗 [Подробнее]({link})                  │
│                                      │
│ {hashtags}
└─────────────────────────────────────┘"""
    
    return message

def format_news(item):
    """Определяет тип новости и форматирует соответственно"""
    news_type = item.get('type', 'general')
    
    if news_type == 'court':
        return format_court_case(item)
    elif news_type == 'seller_story':
        return format_seller_story(item)
    else:
        return format_marketplace_news(item)
