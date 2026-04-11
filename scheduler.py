from datetime import datetime
from typing import Optional, List
import logging
import pytz
import os

logger = logging.getLogger(__name__)

MOSCOW_TZ = pytz.timezone('Europe/Moscow')

MORNING_HOUR = 6
MORNING_WINDOW_END = int(os.getenv("MORNING_WINDOW_END", "9"))  # До 9:00 MSK можно отправить morning digest
EVENING_HOUR = 23

QUIET_HOURS_START = int(os.getenv("QUIET_HOURS_START", "22"))
QUIET_HOURS_END = int(os.getenv("QUIET_HOURS_END", "6"))

ENABLE_MORNING_DIGEST = os.getenv("ENABLE_MORNING_DIGEST", "false").lower() == "true"
ENABLE_EVENING_DIGEST = os.getenv("ENABLE_EVENING_DIGEST", "false").lower() == "true"
ENABLE_AUDIO_DIGEST = os.getenv("ENABLE_AUDIO_DIGEST", "false").lower() == "true"
ENABLE_QUIET_HOURS = os.getenv("ENABLE_QUIET_HOURS", "true").lower() == "true"

_audio_hour = os.getenv("AUDIO_DIGEST_HOUR_MSK", "22")
AUDIO_DIGEST_HOUR = int(_audio_hour) if _audio_hour and _audio_hour.isdigit() else 22

SALUTESPEECH_VOICE = os.getenv("SALUTESPEECH_VOICE") or "Tur_24000"

FORCE_AUDIO_DIGEST = os.getenv("FORCE_AUDIO_DIGEST", "false").lower() == "true"

def now_moscow():
    return datetime.now(MOSCOW_TZ)

def is_quiet_hours() -> bool:
    """Проверяет, сейчас ли Quiet Hours (ночное время, когда regular posts не публикуются)"""
    if not ENABLE_QUIET_HOURS:
        return False
    
    now = now_moscow()
    current_hour = now.hour
    
    if QUIET_HOURS_START == QUIET_HOURS_END:
        return False
    
    if QUIET_HOURS_START > QUIET_HOURS_END:
        return current_hour >= QUIET_HOURS_START or current_hour < QUIET_HOURS_END
    else:
        return QUIET_HOURS_START <= current_hour < QUIET_HOURS_END

def is_morning_time() -> bool:
    now = now_moscow()
    return now.hour >= MORNING_HOUR and now.hour < MORNING_HOUR + 1

def is_evening_time() -> bool:
    now = now_moscow()
    return now.hour >= EVENING_HOUR

def is_audio_digest_time() -> bool:
    now = now_moscow()
    return now.hour >= AUDIO_DIGEST_HOUR

def should_send_morning_digest() -> bool:
    from db import is_digest_sent_today
    
    if not ENABLE_MORNING_DIGEST:
        logger.info("Morning digest disabled by flag")
        return False
    
    if is_digest_sent_today('morning'):
        logger.info("Morning digest already sent today")
        return False
    
    now = now_moscow()
    if MORNING_HOUR <= now.hour < MORNING_WINDOW_END:
        logger.info(f"Morning digest time window matched: {now.hour} in [{MORNING_HOUR}, {MORNING_WINDOW_END})")
        return True
    
    logger.info(f"Morning digest check: now={now.hour}, window=[{MORNING_HOUR}, {MORNING_WINDOW_END}), not in window")
    return False

def should_send_evening_digest() -> bool:
    from db import is_digest_sent_today
    
    if not ENABLE_EVENING_DIGEST:
        logger.info("Evening digest disabled by flag")
        return False
    
    if is_digest_sent_today('evening'):
        logger.info("Evening digest already sent today")
        return False
    
    now = now_moscow()
    if now.hour >= EVENING_HOUR:
        logger.info("First run after evening time, sending digest")
        return True
    
    logger.info(f"Evening digest check: now={now.hour}, target={EVENING_HOUR}, not in window")
    return False

def should_send_audio_digest() -> bool:
    from db import is_digest_sent_today
    
    logger.info(f"force_audio_digest: {str(FORCE_AUDIO_DIGEST).lower()}")
    
    if FORCE_AUDIO_DIGEST:
        logger.info("Audio digest forced via env flag")
        return True
    
    if not ENABLE_AUDIO_DIGEST:
        logger.info("Audio digest disabled by flag")
        return False
    
    if is_digest_sent_today('audio'):
        logger.info("Audio digest already sent today")
        return False
    
    now = now_moscow()
    if now.hour >= AUDIO_DIGEST_HOUR:
        logger.info("First run after audio digest time, sending digest")
        return True
    
    logger.info(f"Audio digest check: now={now.hour}, target={AUDIO_DIGEST_HOUR}, not in window")
    return False

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
        f"{i+1}. {n['title']}\n{n.get('raw_text', '')[:150]}" 
        for i, n in enumerate(top_news[:5])
    ])
    
    script_prompt = f"""Создай сценарий для голосового аудио-дайджеста новостей о маркетплейсах и e-commerce.

Главные новости дня:
{news_text}

Требования к формату:
- Стиль: краткий вечерний выпуск новостей, спокойный деловой тон
- Не читай новости слово в слово - перескажи суть своими словами
- Каждая новость: что произошло (1 предложение) + почему важно для селлера (1-2 предложения)
- Вступление: "Добрый вечер. Это краткий итог дня для селлеров..."
- Завершение: краткий итог дня, 2-3 предложения
- ОБЯЗАТЕЛЬНО: общая длина 280-350 слов, НЕ БОЛЕЕ 400 слов
- Используй короткие предложения, без канцелярита
- Не используй нумерацию вида "1.", "2." - пиши связным текстом
- Каждая новость должна звучать как информация для принятия решений"""

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
                word_count = len(result.split())
                logger.info(f"Generated script word count: {word_count}")
                
                if word_count > 400:
                    logger.warning(f"Script too long ({word_count} words), truncating")
                    words = result.split()
                    result = ' '.join(words[:400])
                
                logger.info("Audio script generated: yes")
                return result
        except Exception as e:
            logger.warning(f"LLM audio script error: {e}")
    
    fallback_text = "Добрый вечер! Вот главные новости дня для продавцов маркетплейсов.\n\n"
    
    for i, n in enumerate(top_news[:5]):
        fallback_text += f"{n['title'][:100]}. "
    
    fallback_text += "\n\nЭто были главные новости. Хорошего дня и успешных продаж!"
    
    logger.info("Audio script generated: fallback")
    return fallback_text

def get_today_date() -> str:
    return datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y")

def wrap_ssml(text: str, voice: str | None = None) -> str:
    """Оборачивает текст в SSML с голосом"""
    if voice is None:
        voice = SALUTESPEECH_VOICE
    
    text = text.replace('^', '')
    
    ssml = f"""<speak>
<voice name="{voice}" lang="ru">
{text}
</voice>
</speak>"""
    return ssml
