from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.models import NewsItem

READ_MORE_MIN_FULL_TEXT_CHARS = 1200
READ_MORE_MIN_EXTRA_CHARS_OVER_POST = 500

IMPORTANT_CATEGORY_LABEL = "🔴 Важно"
ATTENTION_CATEGORY_LABEL = "🟠 Обратите внимание"
GOOD_NEWS_CATEGORY_LABEL = "🟢 Хорошая новость"
ANALYTICS_CATEGORY_LABEL = "🔵 Интересно / аналитика"

APPROVED_CATEGORY_LABELS = (
    IMPORTANT_CATEGORY_LABEL,
    ATTENTION_CATEGORY_LABEL,
    GOOD_NEWS_CATEGORY_LABEL,
    ANALYTICS_CATEGORY_LABEL,
)

_LEGACY_IMPORTANCE_TO_CATEGORY_LABEL = {
    "🔴": IMPORTANT_CATEGORY_LABEL,
    "🟡": ATTENTION_CATEGORY_LABEL,
    "🟠": ATTENTION_CATEGORY_LABEL,
    "🟢": GOOD_NEWS_CATEGORY_LABEL,
    "🔵": ANALYTICS_CATEGORY_LABEL,
}

_NO_DIRECT_ACTION_PHRASES = (
    "Прямых действий пока нет",
    "прямых действий пока нет",
    "прямого действия пока нет",
    "можно просто наблюдать",
    "это скорее фон",
    "фоновый контекст",
)

_CONCRETE_ACTION_TERMS = (
    "штраф", "блокиров", "комисси", "комиссия", "тариф", "выплат", "удержан", "оферт",
    "налог", "фнс", "обязательное правило", "документ", "срок", "отключен", "риск",
)
_EXPLICIT_SELLER_ACTION_TERMS = (
    "проверить конкретн", "проверьте конкретн", "проверить товары", "проверьте товары",
    "подать документ", "подайте документ", "загрузить документ", "изменить карточ", "обновить карточ",
    "оплатить", "учесть комис", "учесть тариф", "комисси", "комиссия", "тариф", "обязательное правило", "обязательное действие", "обязательное требование", "штраф", "блокиров", "отключен",
    "риск штраф", "риск блок", "риск отключ", "срок", "дедлайн",
)
_OPERATIONAL_TERMS = (
    "измен", "запуст", "ввод", "обнов", "правил", "кабинет", "логист", "достав", "возврат",
    "склад", "fbo", "fbs", "приемк", "пвз", "карточ", "отчет", "сертифик", "требован",
)
_POSITIVE_TERMS = ("сниз", "уменьш", "бесплат", "упрост", "улучш", "рост", "повыс", "выгод", "отмен")
_BACKGROUND_TERMS = (
    "статист", "аналит", "исслед", "наблюд", "рынок", "доля", "число", "количество", "сократ", "снизилось",
    "стало меньше", "меньше наруш", "нарушений стало", "по данным", "отчет", "итоги", "динамика", "тренд",
    "говорит, что", "говорят, что", "заранее готовятся", "дорожные карты", "дорожн", "маркетплейсах за год",
)
_BACKGROUND_REGEXES = (
    re.compile(r"нарушен\w*[^.?!]{0,80}стал[оаи]? меньше"),
    re.compile(r"нарушен\w*[^.?!]{0,80}сократил"),
    re.compile(r"количеств[оа] нарушен\w*[^.?!]{0,80}сократ"),
    re.compile(r"маркетплейсах за год"),
    re.compile(r"дорожн\w* карт"),
)
_MARKING_TERMS = ("маркиров", "честный знак", "chestny znak")
_FULL_BEACON_RE = re.compile("|".join(re.escape(label) for label in APPROVED_CATEGORY_LABELS))
_STANDALONE_IMPORTANCE_RE = re.compile(r"(?m)^\s*[🔴🟠🟡🟢🔵]\s*$")
_LEGACY_YELLOW_RE = re.compile("🟡")
_SENTENCE_END_RE = re.compile(r"^[\s:—–\-\.\n]+")


@dataclass
class ReadMoreDecision:
    needed: bool
    reason: str


def _pick_full_text(item: NewsItem) -> str:
    return (getattr(item, "raw_text", None) or getattr(item, "text", None) or "").strip()


def _source_label(item: NewsItem) -> str:
    if getattr(item, "source_name", None):
        return str(item.source_name)
    link = getattr(item, "link", "") or ""
    return (urlparse(link).netloc or "unknown") if link else "unknown"


def _sanitize_regular_post_field(value: object) -> str:
    """Remove beacon/markdown residue from generated text fields before adding one approved label."""
    text = str(value or "")
    text = _FULL_BEACON_RE.sub("", text)
    text = _STANDALONE_IMPORTANCE_RE.sub("", text)
    text = _LEGACY_YELLOW_RE.sub("", text)
    text = text.replace("**", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _html(value: object) -> str:
    return html.escape(str(value or ""), quote=False)


def _indicator_from_label(label: str) -> str:
    return (label or "").strip()[:1]


def _category_label_from_importance(importance: object) -> str | None:
    raw = str(importance or "").strip()
    if raw in APPROVED_CATEGORY_LABELS:
        return raw
    if raw[:1] in _LEGACY_IMPORTANCE_TO_CATEGORY_LABEL:
        return _LEGACY_IMPORTANCE_TO_CATEGORY_LABEL[raw[:1]]
    return None


def _normalize_category_label(label: object) -> str | None:
    raw = str(label or "").strip()
    if not raw:
        return None
    if raw in APPROVED_CATEGORY_LABELS:
        return raw
    return _category_label_from_importance(raw)


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _tags(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    return [part.strip().lower() for part in str(value or "").replace(";", ",").split(",") if part.strip()]


def _haystack(item: NewsItem, seller_result: dict) -> str:
    parts = [
        getattr(item, "title", ""),
        getattr(item, "text", ""),
        getattr(item, "raw_text", ""),
        getattr(item, "processed_text", ""),
        seller_result.get("summary", ""),
        seller_result.get("seller_conclusion", ""),
        seller_result.get("generated_seller_conclusion", ""),
    ]
    return "\n".join(_sanitize_regular_post_field(p) for p in parts).lower().replace("ё", "е")


def _has_any(hay: str, terms: tuple[str, ...]) -> bool:
    return any(term.lower().replace("ё", "е") in hay for term in terms)


def _has_no_direct_action_text(hay: str) -> bool:
    return any(phrase.lower().replace("ё", "е") in hay for phrase in _NO_DIRECT_ACTION_PHRASES)


def _has_strong_background_signal(hay: str) -> bool:
    return _has_any(hay, _BACKGROUND_TERMS) or any(pattern.search(hay) for pattern in _BACKGROUND_REGEXES)


def _has_explicit_seller_action_or_risk(hay: str) -> bool:
    if not _has_any(hay, _EXPLICIT_SELLER_ACTION_TERMS):
        return False
    generic_only = (
        "проверьте, затрагивает ли изменение ваши товары и процессы" in hay
        or "проверьте затрагивает ли изменение ваши товары и процессы" in hay
        or "проверить, затрагивает ли изменение ваши товары и процессы" in hay
    )
    if generic_only and not _has_any(hay, ("штраф", "блокиров", "комисси", "тариф", "документ", "срок", "обязательное правило", "обязательное действие", "обязательное требование", "отключен")):
        return False
    return True


def _strip_title_prefix(body: str, title: str) -> str:
    body = (body or "").strip()
    title = (title or "").strip()
    if not body or not title:
        return body
    norm_body = re.sub(r"\s+", " ", body).lower().replace("ё", "е")
    norm_title = re.sub(r"\s+", " ", title).lower().replace("ё", "е")
    if norm_body.startswith(norm_title):
        stripped = body[len(title):]
        return _SENTENCE_END_RE.sub("", stripped).strip()
    return body


def _deterministic_contract(item: NewsItem, seller_result: dict, body_probe: str = "") -> dict:
    hay = (_haystack(item, seller_result) + "\n" + str(body_probe or "")).lower().replace("ё", "е")
    direct_action_status = str(
        seller_result.get("direct_action_status") or getattr(item, "direct_action_status", "") or "none"
    ).strip()
    seller_relevance = _coerce_int(seller_result.get("seller_relevance_score", getattr(item, "seller_relevance_score", 0)))
    actionability = _coerce_int(seller_result.get("actionability_score", getattr(item, "actionability_score", 0)))
    tags = _tags(seller_result.get("topic_tags", getattr(item, "topic_tags", [])))
    has_concrete = _has_any(hay, _CONCRETE_ACTION_TERMS)
    has_operational = _has_any(hay, _OPERATIONAL_TERMS)
    has_positive = _has_any(hay, _POSITIVE_TERMS)
    has_background = _has_strong_background_signal(hay)
    has_explicit_action = _has_explicit_seller_action_or_risk(hay)
    marking_context = _has_any(hay, _MARKING_TERMS) or any("mark" in t or "маркиров" in t or "legal" in t for t in tags)

    if _has_no_direct_action_text(hay):
        return {
            "category_label": ANALYTICS_CATEGORY_LABEL,
            "category_indicator": "🔵",
            "regular_allowed": False,
            "regular_denial_reason": "no_direct_action_text",
        }

    background_without_action = has_background and not has_explicit_action
    if background_without_action or (marking_context and has_background and not has_explicit_action):
        return {
            "category_label": ANALYTICS_CATEGORY_LABEL,
            "category_indicator": "🔵",
            "regular_allowed": False,
            "regular_denial_reason": "background_without_direct_action",
        }

    requested_label = _normalize_category_label(seller_result.get("category_label"))
    if requested_label is None:
        requested_label = _category_label_from_importance(seller_result.get("category_indicator"))
    if requested_label is None:
        requested_label = _category_label_from_importance(seller_result.get("importance_indicator"))
    if requested_label is None:
        requested_label = _category_label_from_importance(getattr(item, "importance", None))
    if direct_action_status == "direct_action" and actionability >= 6 and seller_relevance >= 6 and has_explicit_action and has_concrete:
        label = IMPORTANT_CATEGORY_LABEL
    elif has_positive and has_explicit_action:
        label = GOOD_NEWS_CATEGORY_LABEL
    elif has_explicit_action:
        label = ATTENTION_CATEGORY_LABEL
    elif requested_label and requested_label != IMPORTANT_CATEGORY_LABEL:
        label = requested_label
    else:
        label = ANALYTICS_CATEGORY_LABEL

    regular_allowed = bool(has_explicit_action) and label != ANALYTICS_CATEGORY_LABEL
    return {
        "category_label": label,
        "category_indicator": _indicator_from_label(label),
        "regular_allowed": regular_allowed,
        "regular_denial_reason": "" if regular_allowed else "background_without_direct_action",
    }


def build_seller_reasoning(item: NewsItem, seller_result: dict | None = None) -> dict:
    """Return legacy-compatible category beacon metadata.

    build_post applies the stricter deterministic regular-post contract; this
    helper remains a small metadata normalizer for older callers/tests.
    """
    seller_result = seller_result or {}
    category_label = _normalize_category_label(seller_result.get("category_label"))
    if category_label is None:
        category_label = _category_label_from_importance(seller_result.get("category_indicator"))
    if category_label is None:
        category_label = _category_label_from_importance(seller_result.get("importance_indicator"))
    if category_label is None:
        category_label = _category_label_from_importance(getattr(item, "importance", None))
    if category_label is None:
        category_label = ATTENTION_CATEGORY_LABEL
    return {"category_label": category_label, "category_indicator": _indicator_from_label(category_label)}


def should_add_read_more_button(item: NewsItem, post_text: str) -> ReadMoreDecision:
    full_text = _pick_full_text(item)
    if not full_text:
        return ReadMoreDecision(False, "full_text_missing")
    if len(full_text) < READ_MORE_MIN_FULL_TEXT_CHARS:
        return ReadMoreDecision(False, "full_text_below_threshold")
    if len(full_text) - len(post_text or "") < READ_MORE_MIN_EXTRA_CHARS_OVER_POST:
        return ReadMoreDecision(False, "full_text_not_materially_longer")
    return ReadMoreDecision(True, "full_text_materially_longer")


def build_post(item: NewsItem, seller_result: dict | None = None) -> dict:
    seller_result = seller_result or {}
    title = _sanitize_regular_post_field(item.title)
    summary_source = seller_result.get("summary") or getattr(item, "summary", "") or (getattr(item, "text", "") or "")[:420]
    summary = _strip_title_prefix(_sanitize_regular_post_field(summary_source), title)
    conclusion_source = seller_result.get("seller_conclusion") or getattr(item, "seller_conclusion", "") or "Что важно селлеру: проверьте, затрагивает ли изменение ваши товары и процессы."
    conclusion = _strip_title_prefix(_sanitize_regular_post_field(conclusion_source), title)
    source_name = _sanitize_regular_post_field(_source_label(item))
    source_url = (getattr(item, "link", "") or "").strip()

    preliminary_body = f"{title}\n{summary}\n{conclusion}"
    reasoning = _deterministic_contract(item, seller_result, preliminary_body)
    category_label = reasoning["category_label"]
    category_indicator = reasoning["category_indicator"]

    body_parts = [f"<b>{_html(title)}</b>"]
    if summary:
        body_parts.append(_html(summary))
    if conclusion:
        body_parts.append(f"Вывод для селлера:\n{_html(conclusion)}")
    body_parts.append(_html(category_label))
    body_parts.append(f"Источник: {_html(source_name)}")
    text = "\n\n".join(part for part in body_parts if part).replace("**", "")

    source_link_present = bool(source_url)
    decision = should_add_read_more_button(item, text)
    callback_payload = f"full_article:{item.news_id}" if decision.needed else None
    callback_button_used = bool(decision.needed and callback_payload)

    return {
        "text": text,
        "button_text": "Читать полностью" if decision.needed else None,
        "callback_payload": callback_payload,
        "forbidden_external_button": True,
        "read_more_button_type": "callback" if decision.needed else "none",
        "read_more_button_text": "Читать полностью" if decision.needed else "",
        "read_more_payload": callback_payload if decision.needed else "",
        "callback_button_used": callback_button_used,
        "source_url_button_used": False,
        "external_url_button_forbidden": True,
        "read_more_needed": decision.needed,
        "read_more_reason": decision.reason,
        "read_more_button_present": decision.needed,
        "read_more_callback_payload_present": bool(callback_payload and callback_payload.startswith("full_article:")),
        "source_link_present": source_link_present,
        "source_url_present": source_link_present,
        "source_name_present": bool(source_name),
        "post_length": len(text),
        "summary_mode": seller_result.get("summary_mode", "rules"),
        "category_label": category_label,
        "category_indicator": category_indicator,
        "regular_allowed": bool(reasoning["regular_allowed"]),
        "regular_denial_reason": reasoning["regular_denial_reason"],
    }

# --- PRODUCTION HOTFIX: hard background/no-action regular gate ---
# Reason: real production candidate 95474 was still allowed as 🟠 regular because
# generic "проверьте, затрагивает ли..." was treated as action. It is not.
try:
    _BUILD_POST_BEFORE_HARD_BACKGROUND_GATE = build_post
except NameError:
    _BUILD_POST_BEFORE_HARD_BACKGROUND_GATE = None


def _insider_norm_text(value):
    return str(value or "").lower().replace("ё", "е")


def _insider_join_candidate_text(item, seller_result, post):
    parts = []
    for attr in ("title", "text", "raw_text", "processed_text", "summary", "source"):
        parts.append(getattr(item, attr, "") or "")
    if isinstance(seller_result, dict):
        for key in ("summary", "seller_conclusion", "post_text", "raw_text", "processed_text", "topic_tags", "direct_action_status"):
            parts.append(seller_result.get(key, "") or "")
    if isinstance(post, dict):
        parts.append(post.get("text", "") or "")
    return _insider_norm_text(" ".join(map(str, parts)))


def _insider_has_any(text, patterns):
    return any(p in text for p in patterns)


def _insider_is_background_without_real_action(text):
    background_patterns = [
        "нарушений с маркировкой",
        "количество нарушений",
        "нарушений стало меньше",
        "стало меньше",
        "сократилось примерно",
        "сократилось",
        "говорит, что",
        "заранее готовятся",
        "дорожные карты",
        "маркетплейсах за год",
        "исследование",
        "статистика",
        "тренд",
        "аналитика",
        "наблюдение",
    ]

    no_action_patterns = [
        "прямых действий пока нет",
        "прямого действия пока нет",
        "можно просто наблюдать",
        "это скорее фон",
        "фоновый контекст",
    ]

    real_action_patterns = [
        "штраф",
        "блокиров",
        "отключ",
        "комисси",
        "тариф",
        "удержан",
        "выплат",
        "оферт",
        "фнс",
        "налог",
        "документ",
        "срок до",
        "до 1",
        "до 2",
        "до 3",
        "до 4",
        "до 5",
        "до 6",
        "до 7",
        "до 8",
        "до 9",
        "обязан",
        "обязательн",
        "нужно подать",
        "нужно изменить",
        "нужно загрузить",
        "проверьте документы",
        "подайте",
        "загрузите",
        "измените карточ",
    ]

    generic_fake_action_patterns = [
        "проверьте, затрагивает ли изменение ваши товары и процессы",
        "проверьте затрагивает ли изменение ваши товары и процессы",
        "что важно селлеру: проверьте",
    ]

    if _insider_has_any(text, no_action_patterns):
        return True

    has_background = _insider_has_any(text, background_patterns)
    has_real_action = _insider_has_any(text, real_action_patterns)
    has_fake_action = _insider_has_any(text, generic_fake_action_patterns)

    # Real 95474 class: marking violations became fewer = analytics/background.
    if "наруш" in text and "маркиров" in text and ("меньше" in text or "сократ" in text):
        return True

    # Background + only generic "check if relevant" is not enough for regular standalone.
    if has_background and (not has_real_action or has_fake_action):
        return True

    return False


def _insider_force_blue_analytics_post(post):
    if not isinstance(post, dict):
        return post

    post["category_label"] = "🔵 Интересно / аналитика"
    post["category_indicator"] = "🔵"
    post["regular_allowed"] = False
    post["regular_denial_reason"] = "background_without_direct_action"
    post["background_without_direct_action"] = True

    text = str(post.get("text") or "")
    text = text.replace("🟠 Обратите внимание", "🔵 Интересно / аналитика")
    text = text.replace("🔴 Важно", "🔵 Интересно / аналитика")
    text = text.replace("**", "")
    post["text"] = text
    return post


def build_post(item, seller_result=None):
    post = _BUILD_POST_BEFORE_HARD_BACKGROUND_GATE(item, seller_result)
    text = _insider_join_candidate_text(item, seller_result or {}, post)
    if _insider_is_background_without_real_action(text):
        return _insider_force_blue_analytics_post(post)
    return post
# --- /PRODUCTION HOTFIX ---
