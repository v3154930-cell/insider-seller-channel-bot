from datetime import datetime
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

MORNING_HOUR = 6
EVENING_HOUR = 23
TIME_WINDOW = 5

def is_morning() -> bool:
    now = datetime.now()
    return abs(now.hour - MORNING_HOUR) <= TIME_WINDOW and now.minute <= TIME_WINDOW

def is_evening() -> bool:
    now = datetime.now()
    return abs(now.hour - EVENING_HOUR) <= TIME_WINDOW and now.minute <= TIME_WINDOW

def is_morning_time() -> bool:
    now = datetime.now()
    return now.hour == MORNING_HOUR and now.minute <= TIME_WINDOW

def is_evening_time() -> bool:
    now = datetime.now()
    return now.hour == EVENING_HOUR and now.minute <= TIME_WINDOW

def get_morning_summary() -> Optional[str]:
    from db import get_critical_news_hours
    from llm import enhance_post_with_llm, USE_LLM
    
    critical_news = get_critical_news_hours(hours=24)
    
    if not critical_news:
        return "🌅 Доброе утро! Ночь прошла спокойно, важных изменений нет.\nХорошего дня! ☀️"
    
    if USE_LLM:
        summary_text = "\n\n".join([
            f"• {n['title']}" for n in critical_news[:5]
        ])
        
        from llm import GITHUB_TOKEN
        if GITHUB_TOKEN:
            try:
                from llm import enhance_post_with_llm
                prompt = f"""Создай утреннюю сводку для канала о маркетплейсах. 

Новости за ночь:
{summary_text}

Формат:
🌅 Доброе утро! За ночь произошли изменения:
[кратко 2-3 предложения о главном]
Хорошего дня! ☀️"""

                result = enhance_post_with_llm({
                    'title': 'Утренняя сводка',
                    'raw_text': summary_text,
                    'link': '',
                    'source': 'Бот',
                    'category': 'summary'
                })
                
                if result:
                    return result
            except Exception as e:
                logger.warning(f"LLM morning summary error: {e}")
    
    critical_items = "\n".join([
        f"• {n['title'][:100]}" for n in critical_news[:5]
    ])
    
    return f"""🌅 Доброе утро! За ночь произошли изменения:

{critical_items}

Хорошего дня! ☀️"""

def get_evening_digest() -> Optional[str]:
    from db import get_today_published
    
    today_news = get_today_published()
    critical = [n for n in today_news if n.get('importance') in ('critical', 'high')]
    
    if not today_news:
        return "📋 ВЕЧЕРНИЙ ДАЙДЖЕСТ | {date}\n\nДень прошёл продуктивно, значимых изменений не произошло.\nДоброй ночи! 🌙"
    
    from llm import enhance_post_with_llm, USE_LLM, GITHUB_TOKEN
    
    if USE_LLM and GITHUB_TOKEN and critical:
        summary_text = "\n\n".join([
            f"• {n['title']}" for n in critical[:7]
        ])
        
        try:
            result = enhance_post_with_llm({
                'title': 'Вечерний дайджест',
                'raw_text': summary_text,
                'link': '',
                'source': 'Бот',
                'category': 'digest'
            })
            
            if result:
                return result
        except Exception as e:
            logger.warning(f"LLM evening digest error: {e}")
    
    date = datetime.now().strftime("%d.%m.%Y")
    
    if critical:
        critical_items = "\n".join([
            f"🔴 *{n['title'][:80]}*" for n in critical[:3]
        ])
        return f"""📋 ВЕЧЕРНИЙ ДАЙДЖЕСТ | {date}

🔴 КРИТИЧНО:
{critical_items}

Всего опубликовано: {len(today_news)} новостей
Доброй ночи! 🌙"""
    
    return f"""📋 ВЕЧЕРНИЙ ДАЙДЖЕСТ | {date}

День прошёл продуктивно, значимых изменений не произошло.

Опубликовано: {len(today_news)} новостей
Доброй ночи! 🌙"""

def get_today_date() -> str:
    return datetime.now().strftime("%d.%m.%Y")