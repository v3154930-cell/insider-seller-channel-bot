from datetime import datetime
from typing import Optional, List
import logging
import pytz

logger = logging.getLogger(__name__)

MOSCOW_TZ = pytz.timezone('Europe/Moscow')

MORNING_HOUR = 6
EVENING_HOUR = 23
AUDIO_HOUR = 22
TIME_WINDOW = 5

ENABLE_MORNING_DIGEST = True
ENABLE_EVENING_DIGEST = True
ENABLE_AUDIO_DIGEST = True

def now_moscow():
    return datetime.now(MOSCOW_TZ)

def is_morning_time() -> bool:
    now = now_moscow()
    return now.hour == MORNING_HOUR and now.minute <= TIME_WINDOW

def is_evening_time() -> bool:
    now = now_moscow()
    return now.hour == EVENING_HOUR and now.minute <= TIME_WINDOW

def is_audio_digest_time() -> bool:
    now = now_moscow()
    return now.hour == AUDIO_HOUR and now.minute <= TIME_WINDOW

def should_send_morning_digest() -> bool:
    from db import is_digest_sent_today
    
    if not ENABLE_MORNING_DIGEST:
        logger.info("Morning digest disabled by flag")
        return False
    
    if is_digest_sent_today('morning'):
        logger.info("Morning digest already sent today")
        return False
    
    return is_morning_time()

def should_send_evening_digest() -> bool:
    from db import is_digest_sent_today
    
    if not ENABLE_EVENING_DIGEST:
        logger.info("Evening digest disabled by flag")
        return False
    
    if is_digest_sent_today('evening'):
        logger.info("Evening digest already sent today")
        return False
    
    return is_evening_time()

def should_send_audio_digest() -> bool:
    from db import is_digest_sent_today
    
    if not ENABLE_AUDIO_DIGEST:
        logger.info("Audio digest disabled by flag")
        return False
    
    if is_digest_sent_today('audio'):
        logger.info("Audio digest already sent today")
        return False
    
    return is_audio_digest_time()

def get_morning_summary() -> Optional[str]:
    from db import get_critical_news_hours, set_digest_sent
    from llm import enhance_post_with_llm, USE_LLM
    
    logger.info("Morning digest check: yes")
    
    critical_news = get_critical_news_hours(hours=24)
    logger.info(f"Selected top news for digest: {len(critical_news)}")
    
    if not critical_news:
        result = "🌅 Доброе утро! Ночь прошла спокойно, важных изменений нет.\nХорошего дня! ☀️"
        set_digest_sent('morning')
        return result
    
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
                    set_digest_sent('morning')
                    return result
            except Exception as e:
                logger.warning(f"LLM morning summary error: {e}")
    
    critical_items = "\n".join([
        f"• {n['title'][:100]}" for n in critical_news[:5]
    ])
    
    result = f"""🌅 Доброе утро! За ночь произошли изменения:

{critical_items}

Хорошего дня! ☀️"""
    
    set_digest_sent('morning')
    return result

def get_evening_digest() -> Optional[str]:
    from db import get_today_published, set_digest_sent, mark_news_in_digest
    
    logger.info("Evening digest check: yes")
    
    today_news = get_today_published()
    logger.info(f"Selected top news for digest: {len(today_news)}")
    
    if not today_news:
        date = datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y")
        result = f"📋 ВЕЧЕРНИЙ ДАЙДЖЕСТ | {date}\n\nДень прошёл продуктивно, значимых изменений не произошло.\nДоброй ночи! 🌙"
        set_digest_sent('evening')
        return result
    
    from llm import enhance_post_with_llm, USE_LLM, GITHUB_TOKEN
    critical = [n for n in today_news if n.get('importance') in ('critical', 'high')]
    
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
                news_ids = [n['id'] for n in critical[:7]]
                mark_news_in_digest(news_ids)
                set_digest_sent('evening')
                return result
        except Exception as e:
            logger.warning(f"LLM evening digest error: {e}")
    
    date = datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y")
    
    if critical:
        critical_items = "\n".join([
            f"🔴 *{n['title'][:80]}*" for n in critical[:3]
        ])
        result = f"""📋 ВЕЧЕРНИЙ ДАЙДЖЕСТ | {date}

🔴 КРИТИЧНО:
{critical_items}

Всего опубликовано: {len(today_news)} новостей
Доброй ночи! 🌙"""
    else:
        result = f"""📋 ВЕЧЕРНИЙ ДАЙДЖЕСТ | {date}

День прошёл продуктивно, значимых изменений не произошло.

Опубликовано: {len(today_news)} новостей
Доброй ночи! 🌙"""
    
    set_digest_sent('evening')
    return result

def get_audio_digest_script(top_news: List[dict]) -> Optional[str]:
    """Генерирует сценарий для аудио-дайджеста"""
    from llm import enhance_post_with_llm, USE_LLM, GITHUB_TOKEN
    
    logger.info("Audio script generation check: yes")
    
    if not top_news:
        return None
    
    news_text = "\n\n".join([
        f"{i+1}. {n['title']}\n{n.get('raw_text', '')[:200]}" 
        for i, n in enumerate(top_news[:5])
    ])
    
    script_prompt = f"""Создай сценарий для голосового аудио-дайджеста новостей о маркетплейсах.

Главные новости дня:
{news_text}

Требования к формату:
- Разговорный, спокойный русский язык
- Не читай новости слово в слово - перескажи своими словами
- Каждая новость: что произошло и почему важно для селлеров
- Вступление: "Добрый вечер! Вот главные новости дня для продавцов..."
- Завершение: "Это были главные новости. Хорошего дня и успешных продаж!"
- Общая длительность текста - примерно на 2-3 минуты чтения
- Используй простые предложения, без сложных терминов"""

    if USE_LLM and GITHUB_TOKEN:
        try:
            result = enhance_post_with_llm({
                'title': 'Аудио дайджест',
                'raw_text': script_prompt,
                'link': '',
                'source': 'Бот',
                'category': 'audio_digest'
            })
            
            if result:
                logger.info("Audio script generated: yes")
                return result
        except Exception as e:
            logger.warning(f"LLM audio script error: {e}")
    
    fallback_text = "Добрый вечер! Вот главные новости дня для продавцов маркетплейсов.\n\n"
    
    for i, n in enumerate(top_news[:5]):
        fallback_text += f"{i+1}. {n['title']}.\n"
    
    fallback_text += "\nЭто были главные новости. Хорошего дня и успешных продаж!"
    
    logger.info("Audio script generated: fallback")
    return fallback_text

def get_today_date() -> str:
    return datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y")
