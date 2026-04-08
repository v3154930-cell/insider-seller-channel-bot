import os
import logging
from typing import Dict, Optional, List
import requests

logger = logging.getLogger(__name__)

USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")

LLM_API_URL = "https://models.github.ai/inference"
GPT4O_MINI_MODEL = "gpt-4o"

logger.info("=== LLM Module Initialization ===")
logger.info(f"[LLM] USE_LLM enabled: {USE_LLM}")
logger.info(f"[LLM] Token source: {'GITHUB_TOKEN' if GITHUB_TOKEN else 'GH_TOKEN' if os.getenv('GH_TOKEN') else 'NONE'}")
logger.info(f"[LLM] GITHUB_TOKEN configured: {bool(GITHUB_TOKEN)}")
logger.info(f"[LLM] API endpoint: {LLM_API_URL}")

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

def smoke_test_llm() -> bool:
    """Smoke test for GitHub Models API"""
    if not GITHUB_TOKEN:
        logger.warning("[LLM] Smoke test: no token")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json"
        }
        payload = {
            "model": GPT4O_MINI_MODEL,
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 1
        }
        response = requests.post(
            LLM_API_URL + "/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        logger.info(f"[LLM] Smoke test HTTP: {response.status_code}")
        if response.status_code == 200:
            logger.info("[LLM] Smoke test: SUCCESS")
            return True
        elif response.status_code == 403:
            error_detail = response.json().get('error', {}).get('details', '')
            logger.warning(f"[LLM] Smoke test: 403 - {error_detail}")
            if 'no_access' in error_detail.lower() or 'gpt-4o-mini' in error_detail.lower():
                logger.warning("[LLM] Smoke test: gpt-4o-mini not available, trying gpt-4o")
                payload["model"] = "gpt-4o"
                response = requests.post(
                    LLM_API_URL + "/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info("[LLM] Smoke test: SUCCESS with gpt-4o")
                    return True
        return False
    except Exception as e:
        logger.warning(f"[LLM] Smoke test: {e}")
        return False

def enhance_post_with_llm(raw_news: Dict) -> Optional[str]:
    logger.info("[LLM] ===== START enhance_post_with_llm =====")
    
    if not USE_LLM:
        logger.info("[LLM] USE_LLM=false, returning None for fallback")
        return None
    
    if not GITHUB_TOKEN:
        logger.warning("[LLM] No GITHUB_TOKEN, returning None for fallback")
        return None
    
    title = raw_news.get('title', '')
    raw_text = raw_news.get('raw_text', raw_news.get('description', ''))
    link = raw_news.get('link', '')
    source = raw_news.get('source', 'Новость')
    category = raw_news.get('category', 'general')
    
    logger.info(f"[LLM] Processing: {title[:40]}...")
    logger.info("[LLM] Attempting GitHub Models API call...")
    
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
        logger.info("[LLM] Calling GitHub Models API...")
        response = requests.post(
            LLM_API_URL + "/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        logger.info(f"[LLM] Response HTTP: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            if content:
                logger.info("[LLM] SUCCESS - post enhanced")
                return content
            else:
                logger.warning("[LLM] Empty response content")
        elif response.status_code == 403:
            logger.warning("[LLM] 403 Forbidden - check token permissions for GitHub Models")
        else:
            logger.warning(f"[LLM] API Error: {response.status_code} - {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        logger.warning("[LLM] Request timeout")
    except requests.exceptions.RequestException as e:
        logger.warning(f"[LLM] Request error: {e}")
    except Exception as e:
        logger.warning(f"[LLM] Unexpected error: {e}")
    
    logger.info("[LLM] Fallback to standard formatter")
    return None