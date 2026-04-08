import os
import logging
from typing import Dict, Optional, List
import requests

logger = logging.getLogger(__name__)

USE_LLM = os.getenv("USE_LLM", "true").lower() == "true"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

LLM_API_URL = "https://models.github.ai/inference"
GPT4O_MINI_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """Ты редактор канала о маркетплейсах (Ozon, Wildberries, Яндекс Маркет). 
Твоя задача — переписать новость в формате для телеграм-канала.

Формат поста:
📦 **Источник**
**Заголовок**
Краткий пересказ (150-200 символов)
💡 Суть: одна фраза
🔗 Подробнее: ссылка
Добавь эмодзи по теме: 💰 комиссии, 🚚 логистика, ⚖️ законы, 🎁 акции, ⚖️ суды

Правила:
- Кратко и по делу
- Без воды
- Один ключевой вывод
- Используй эмодзи для визуального разделения"""

def enhance_post_with_llm(raw_news: Dict) -> str:
    if not USE_LLM:
        return None
    
    if not GITHUB_TOKEN:
        logger.warning("GITHUB_TOKEN not set, skipping LLM")
        return None
    
    title = raw_news.get('title', '')
    raw_text = raw_news.get('raw_text', raw_news.get('description', ''))
    link = raw_news.get('link', '')
    source = raw_news.get('source', 'Новость')
    category = raw_news.get('category', 'general')
    
    user_prompt = f"""Перепиши эту новость:

Источник: {source}
Заголовок: {title}
Текст: {raw_text[:500]}
Ссылка: {link}
Категория: {category}

Требуемый формат вывода:
📦 **Источник**
**Заголовок**
Краткий пересказ (150-200 символов)
💡 Суть: одна фраза
🔗 [Подробнее](ссылка)
#хештеги"""

    payload = {
        "model": GPT4O_MINI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            LLM_API_URL + "/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            if content:
                logger.info(f"LLM enhanced post successfully")
                return content
        else:
            logger.warning(f"LLM API error: {response.status_code} - {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        logger.warning("LLM request timeout")
    except requests.exceptions.RequestException as e:
        logger.warning(f"LLM request error: {e}")
    except Exception as e:
        logger.warning(f"LLM unexpected error: {e}")
    
    return None

def enhance_batch(news_list: List[Dict]) -> List[Dict]:
    if not USE_LLM:
        return news_list
    
    enhanced = []
    for news in news_list:
        enhanced_text = enhance_post_with_llm(news)
        if enhanced_text:
            news['processed_text'] = enhanced_text
        enhanced.append(news)
    
    return enhanced