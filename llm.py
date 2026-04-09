import os
import json
import logging
from typing import Dict, Optional, List
import requests

logger = logging.getLogger(__name__)

USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"
SELLER_FILTER_MODE = (os.getenv("SELLER_FILTER_MODE") or "off").lower()
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "github_models").lower()
LLM_MODEL = os.getenv("LLM_MODEL") or "gpt-4o-mini"
GITHUB_MODELS_TOKEN = os.getenv("GITHUB_MODELS_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")

GITHUB_MODELS_API_URL = "https://models.github.ai/inference"
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if GITHUB_MODELS_TOKEN:
    ACTUAL_TOKEN = GITHUB_MODELS_TOKEN
    AUTH_MODE = "github_models_token"
elif GITHUB_TOKEN:
    ACTUAL_TOKEN = GITHUB_TOKEN
    AUTH_MODE = "github_actions_token"
else:
    ACTUAL_TOKEN = None
    AUTH_MODE = "none"

logger.info("LLM provider: " + LLM_PROVIDER)
logger.info("LLM auth: " + AUTH_MODE)
logger.info("Seller filter mode: " + SELLER_FILTER_MODE)

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
    if not ACTUAL_TOKEN:
        logger.warning("LLM smoke test: no token")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {ACTUAL_TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json"
        }
        payload = {
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 1
        }
        response = requests.post(
            GITHUB_MODELS_API_URL + "/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        logger.info("LLM smoke test HTTP: " + str(response.status_code))
        if response.status_code == 200:
            logger.info("LLM smoke test: SUCCESS")
            return True
        return False
    except Exception as e:
        logger.warning("LLM smoke test: " + str(e))
        return False

def enhance_post_with_llm(raw_news: Dict) -> Optional[str]:
    if not USE_LLM:
        return None
    
    if not ACTUAL_TOKEN:
        logger.warning("LLM enhance: no token")
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
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    headers = {
        "Authorization": f"Bearer {ACTUAL_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            GITHUB_MODELS_API_URL + "/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            if content:
                return content
        elif response.status_code == 403:
            logger.warning("LLM enhance: 403 - check token permissions")
        else:
            logger.warning("LLM enhance: HTTP " + str(response.status_code))
            
    except requests.exceptions.Timeout:
        logger.warning("LLM enhance: timeout")
    except requests.exceptions.RequestException as e:
        logger.warning("LLM enhance: request error - " + str(e))
    
    return None

SELLER_RELEVANCE_SYSTEM_PROMPT = """Ты — редактор Telegram-канала для селлеров маркетплейсов и товарного бизнеса.
Твоя задача — оценивать новости только с точки зрения практической пользы для продавцов.

Пропускай новости, если они влияют на продажи, маржу, комиссии, логистику, поставки, рекламу, правила маркетплейсов, маркировку, налоги, спрос, поведение покупателей или инструменты для продавцов.
Отбрасывай новости, которые являются просто общим новостным фоном, политикой, международной повесткой или инфраструктурными событиями без прямого эффекта на селлеров.
Всегда думай как редактор канала для продавцов: если из новости нельзя сделать полезный вывод "что это значит для селлера", такая новость не подходит для отдельного поста.
Отвечай только валидным JSON без markdown и без дополнительных комментариев."""

SELLER_RELEVANCE_USER_PROMPT_TEMPLATE = """Оцени эту новость для Telegram-канала селлеров маркетплейсов:

Заголовок: {title}
Текст: {raw_text}
Источник: {source}
Ссылка: {link}

Ответь СТРОГО в формате JSON без markdown:
{{
  "decision": "publish" | "digest" | "drop",
  "seller_relevance_score": 0-10,
  "actionability_score": 0-10,
  "category": "marketplace_rules" | "commissions_fees" | "logistics_fulfillment" | "ads_promotion" | "taxes_regulation" | "labeling_compliance" | "import_supply" | "consumer_demand" | "category_trends" | "tools_automation_ai" | "ecommerce_market" | "other",
  "reason": "краткое объяснение",
  "seller_impact": "что это значит для селлера",
  "action_hint": "что стоит сделать/учесть селлеру (если нет - пустая строка)"
}}"""

def evaluate_seller_relevance(raw_news: Dict) -> Optional[Dict]:
    """Оценивает новость по релевантности для селлеров. Возвращает dict с решением или None при ошибке."""
    if not USE_LLM:
        logger.info("Seller filter: off (USE_LLM=false)")
        return None
    
    if not ACTUAL_TOKEN:
        logger.warning("Seller filter: no token available")
        return None
    
    title = raw_news.get('title', '')
    raw_text = raw_news.get('raw_text', raw_news.get('description', ''))
    source = raw_news.get('source', 'Новость')
    link = raw_news.get('link', '')
    
    user_prompt = SELLER_RELEVANCE_USER_PROMPT_TEMPLATE.format(
        title=title[:200],
        raw_text=raw_text[:800] if raw_text else '',
        source=source,
        link=link
    )
    
    headers = {
        "Authorization": f"Bearer {ACTUAL_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json"
    }
    
    if LLM_PROVIDER == "openai" and OPENAI_API_KEY:
        api_url = OPENAI_API_URL + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
    else:
        api_url = GITHUB_MODELS_API_URL + "/chat/completions"
    
    logger.info(f"LLM request: provider={LLM_PROVIDER}, model={LLM_MODEL}, url={api_url}")
    
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SELLER_RELEVANCE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 400
    }
    
    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            logger.info("LLM request ok")
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            if content:
                content = content.strip()
                if content.startswith('```json'):
                    content = content[7:]
                if content.startswith('```'):
                    content = content[3:]
                if content.endswith('```'):
                    content = content[:-3]
                content = content.strip()
                
                parsed = json.loads(content)
                
                decision = parsed.get('decision', 'digest')
                relevance = parsed.get('seller_relevance_score', 0)
                actionability = parsed.get('actionability_score', 0)
                
                if decision not in ['publish', 'digest', 'drop']:
                    decision = 'digest'
                if not isinstance(relevance, int) or not (0 <= relevance <= 10):
                    relevance = 0
                if not isinstance(actionability, int) or not (0 <= actionability <= 10):
                    actionability = 0
                
                logger.info(f"Seller filter: decision={decision}, relevance={relevance}, actionability={actionability}")
                return {
                    'decision': decision,
                    'seller_relevance_score': relevance,
                    'actionability_score': actionability,
                    'category': parsed.get('category', 'other'),
                    'reason': parsed.get('reason', ''),
                    'seller_impact': parsed.get('seller_impact', ''),
                    'action_hint': parsed.get('action_hint', '')
                }
        elif response.status_code == 401 or response.status_code == 403:
            logger.warning(f"LLM request failed: {response.status_code} - auth error")
        else:
            logger.warning(f"LLM request failed: HTTP {response.status_code} - {response.text[:200] if response.text else 'no body'}")
            
    except json.JSONDecodeError as e:
        logger.warning(f"Seller filter JSON parse error: {e}")
    except requests.exceptions.Timeout:
        logger.warning("LLM request failed: timeout")
    except requests.exceptions.RequestException as e:
        logger.warning(f"LLM request failed: {e}")
    except Exception as e:
        logger.warning(f"LLM request failed: unexpected - {e}")
    
    return None

def select_best_items_for_publishing(items: List[Dict], max_select: int = 2) -> Optional[List[Dict]]:
    """Selects best 1-2 items for publishing from candidate list using LLM batch evaluation."""
    if not USE_LLM:
        logger.info("Batch selection: off (USE_LLM=false), returning items as-is")
        return items[:max_select] if items else None
    
    if not ACTUAL_TOKEN:
        logger.warning("Batch selection: no token, returning items as-is")
        return items[:max_select] if items else None
    
    if not items:
        logger.info("Batch selection: no items to select from")
        return None
    
    items_list = []
    for i, item in enumerate(items):
        items_list.append(f"""
{i+1}. Заголовок: {item.get('title', '')[:100]}
   Источник: {item.get('source', 'Новость')}
   Текст: {(item.get('raw_text') or item.get('description') or '')[:300]}
   Ссылка: {item.get('link', '')}
""")
    
    items_text = "\n".join(items_list)
    
    batch_system_prompt = """Ты — редактор Telegram-канала для селлеров маркетплейсов.
Из списка новостей выбери ТОЛЬКО те, которые будут наиболее полезны для селлеров.
Считай только score relevance для селлеров, не importance от источника.
Выбери 1-2 самые важные новости для продавцов маркетплейсов (комиссии, логистика, правила, налоги, реклама, поставки, спрос и т.д.).
Ответь СТРОГО в формате JSON без markdown."""

    batch_user_prompt = f"""Из этого списка выбери {max_select} лучших новостей для канала селлеров:

{items_text}

Ответь СТРОГО в формате JSON:
{{
  "selected_indices": [номера через запятую, например "1,3"],
  "reason": "краткое объяснение выбора"
}}
Выбери {max_select} новостей с наибольшей практической пользой для селлеров."""

    headers = {
        "Authorization": f"Bearer {ACTUAL_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json"
    }
    
    if LLM_PROVIDER == "openai" and OPENAI_API_KEY:
        api_url = OPENAI_API_URL + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
    else:
        api_url = GITHUB_MODELS_API_URL + "/chat/completions"
    
    logger.info(f"Batch selection: evaluating {len(items)} items")
    
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": batch_system_prompt},
            {"role": "user", "content": batch_user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 300
    }
    
    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=45
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            if content:
                content = content.strip()
                if content.startswith('```json'):
                    content = content[7:]
                if content.startswith('```'):
                    content = content[3:]
                if content.endswith('```'):
                    content = content[:-3]
                content = content.strip()
                
                parsed = json.loads(content)
                selected_indices = parsed.get('selected_indices', '')
                reason = parsed.get('reason', '')

                logger.info(f"Batch selection: reason={reason}")

                index_list = []
                indices_source = ""

                if isinstance(selected_indices, list):
                    indices_source = "repaired"
                    logger.info(f"Batch selection: indices received as list: {selected_indices}")
                    for idx in selected_indices:
                        try:
                            if isinstance(idx, int):
                                idx_zero_based = idx - 1
                                if 0 <= idx_zero_based < len(items):
                                    index_list.append(idx_zero_based)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Batch selection: idx parse error {idx}: {e}")
                elif isinstance(selected_indices, str) and selected_indices:
                    indices_source = "original"
                    for part in selected_indices.split(','):
                        try:
                            idx = int(part.strip()) - 1
                            if 0 <= idx < len(items):
                                index_list.append(idx)
                        except (ValueError, TypeError):
                            pass
                else:
                    logger.warning("Batch selection: invalid response, skipping run")
                    return None

                if not index_list:
                    logger.warning(f"Batch selection: no valid indices, items={len(items)}, index_list={index_list}")
                    return None

                logger.info(f"Batch selection: indices parsed, count={len(index_list)}, indices={index_list}")

                if indices_source == "repaired":
                    logger.info("Batch selection: parse repaired")
                else:
                    logger.info("Batch selection: ok")
        else:
            logger.warning(f"Batch selection failed: HTTP {response.status_code}")
            
    except json.JSONDecodeError as e:
        logger.warning(f"Batch selection JSON parse error: {e}")
    except requests.exceptions.Timeout:
        logger.warning("Batch selection: timeout")
    except Exception as e:
        logger.warning(f"Batch selection failed: {e}")
    
    logger.warning("Batch selection: failed, skipping run")
    return None