import json
from pathlib import Path
from typing import Dict, Any


RULES_PATH = Path(__file__).parent / "config" / "seller_filter_rules.json"


def norm(value: Any) -> str:
    return str(value or "").lower().replace("ё", "е")


def item_text(item: Dict[str, Any]) -> str:
    return " ".join([
        norm(item.get("title")),
        norm(item.get("raw_text")),
        norm(item.get("description")),
        norm(item.get("summary")),
        norm(item.get("source")),
        norm(item.get("link")),
    ])


def load_rules() -> Dict[str, list]:
    try:
        return json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {
            "hard_drop": [],
            "publish_strong": [],
            "digest_medium": [],
            "weak_ignore": []
        }


def find_matches(text: str, phrases: list) -> list:
    """
    Safer matching:
    - long multi-word phrases may match as substrings;
    - short tokens like "фас", "суд", "ндс" must match as separate words;
    - this prevents false positives like "фас" inside "классифайд".
    """
    import re

    result = []
    for phrase in phrases:
        p = norm(phrase).strip()
        if not p:
            continue

        # For short single-word tokens require word boundaries.
        if " " not in p and len(p) <= 4:
            pattern = r"(?<![a-zа-я0-9])" + re.escape(p) + r"(?![a-zа-я0-9])"
            if re.search(pattern, text, flags=re.IGNORECASE):
                result.append(phrase)
            continue

        if p in text:
            result.append(phrase)

    return result


def _evaluate_item_raw(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dry-run seller filter.

    Decisions:
    - drop: obvious spam/noise
    - publish: strong seller impact
    - digest: useful but not enough for separate post
    - ignore: weak/non-actionable
    """
    rules = load_rules()
    text = item_text(item)

    hard = find_matches(text, rules.get("hard_drop", []))
    if hard:
        return {
            "decision": "drop",
            "seller_relevance_score": 0,
            "actionability_score": 0,
            "reason": "hard_drop: " + ", ".join(hard[:5])
        }

    weak = find_matches(text, rules.get("weak_ignore", []))
    strong = find_matches(text, rules.get("publish_strong", []))
    medium = find_matches(text, rules.get("digest_medium", []))

    if strong:
        score = min(10, 4 + len(strong) + min(len(medium), 2))
        return {
            "decision": "publish",
            "seller_relevance_score": score,
            "actionability_score": min(10, score),
            "reason": "publish_strong: " + ", ".join(strong[:5])
        }

    if medium and not weak:
        score = min(5, 1 + len(medium))
        return {
            "decision": "digest",
            "seller_relevance_score": score,
            "actionability_score": max(1, min(3, score)),
            "reason": "digest_medium: " + ", ".join(medium[:5])
        }

    if weak:
        return {
            "decision": "ignore",
            "seller_relevance_score": 0,
            "actionability_score": 0,
            "reason": "weak_ignore: " + ", ".join(weak[:5])
        }

    return {
        "decision": "ignore",
        "seller_relevance_score": 0,
        "actionability_score": 0,
        "reason": "no_rule_match"
    }


# === SELLER_FILTER_HARD_IGNORE_PATCH_V1 ===
_HARD_IGNORE_TEXT_PARTS = [
    # Реклама, партнёрки, рефки, крипта, торговые сигналы.
    "для наших резидентов",
    "существенно снизить налоговые расходы",
    "с нами вы сможете получить",
    "whitebird",
    "signup?refid",
    "refid=",
    "байбит",
    "bybit",
    "закрытом чате",
    "торговый сигнал",
    "бонусного копирования",
    "крипто обменник",
    "криптообменник",

    # Подборки/каналы/самореклама.
    "у вас разбегаются глаза",
    "огромного количества каналов",
    "на какие из них подписаться",
    "подписаться, чтобы регулярно",
    "e-com база, к которой ты будешь возвращаться",

    # Старые бюллетени, которые не должны становиться отдельной новостью.
    "epharma-бюллетень",
    "egrocery бюллетень",
]


def _hard_ignore_text(item):
    if not isinstance(item, dict):
        return ""

    parts = []
    for key in ("title", "description", "raw_text", "processed_text", "content", "text", "source", "link", "url"):
        value = item.get(key)
        if value:
            parts.append(str(value))

    return " ".join(parts).lower()


def evaluate_item(item):
    """
    Боевой wrapper поверх основного seller_filter.

    Цель: рекламный/партнёрский мусор не должен становиться publish даже если внутри
    встречаются слова вроде НДС, тарифы, маркетплейсы, селлеры.
    """
    text = _hard_ignore_text(item)

    for bad in _HARD_IGNORE_TEXT_PARTS:
        if bad in text:
            return {
                "decision": "ignore",
                "seller_relevance_score": 0,
                "actionability_score": 0,
                "reason": "hard_ignore_ad_or_spam: " + bad,
            }

    return _evaluate_item_raw(item)

