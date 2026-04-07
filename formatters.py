import re
from filters import extract_amounts

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
    
    emoji = emoji_map.get(news_type, '📰')
    
    title = item['title']
    description = item['description']
    
    if len(description) > 200:
        description = description[:197] + "..."
    
    link = item.get('link', '')
    
    message = f"{emoji} {source}\n\n"
    message += f"**{title}**\n\n"
    message += f"{description}\n\n"
    message += f"[Читать полностью]({link})"
    
    return message

def format_court_case(item):
    """Форматирует судебный кейс"""
    title = item['title']
    description = item.get('description', '')
    link = item.get('link', '')
    source = item.get('source', 'Суд')
    
    amounts = extract_amounts(f"{title} {description}")
    amount_str = amounts[0] if amounts else "не указана"
    
    message = f"⚖️ СУДЕБНЫЙ КЕЙС | {source}\n\n"
    message += f"**Суть дела:** {title[:200]}\n\n"
    message += f"📊 Результат: Взыскано {amount_str}\n\n"
    
    if description:
        message += f"📌 Вывод: {description[:150]}\n\n"
    
    message += f"🔗 [Источник]({link})"
    
    return message

def format_seller_story(item):
    """Форматирует историю селлера"""
    title = item['title']
    description = item.get('description', '')
    link = item.get('link', '')
    source = item.get('source', 'История')
    
    amounts = extract_amounts(f"{title} {description}")
    
    message = f"💡 ИСТОРИЯ УСПЕХА | {source}\n\n"
    message += f"**{title}**\n\n"
    message += f"{description[:200] if description else 'Полезный опыт селлера'}\n\n"
    
    if amounts:
        message += f"📊 Результат: {amounts[0]}\n\n"
    
    message += f"🎯 Урок: {description[50:150] if len(description) > 50 else 'Бизнес-опыт'}\n\n"
    message += f"🔗 [Подробнее]({link})"
    
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