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
    summary_source = seller_result.get("summary") or getattr(item, "summary", "") or (getattr(item, "text", "") or "")[:900]
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

# --- PRODUCTION HOTFIX: traffic-light category and seller takeaway v2 ---
# Goal:
# - make 🔴/🟠/🟢/🔵 consistent;
# - replace generic seller takeaway with topic-specific advice;
# - classify positive marketplace opportunities as 🟢, analytics as 🔵, risks as 🔴, operations as 🟠.
try:
    _BUILD_POST_BEFORE_TRAFFIC_LIGHT_TAKEAWAYS_V2 = build_post
except NameError:
    _BUILD_POST_BEFORE_TRAFFIC_LIGHT_TAKEAWAYS_V2 = None


def _tl_norm_v2(value):
    try:
        return str(value or "").lower().replace("ё", "е")
    except Exception:
        return ""


def _tl_any_v2(text, tokens):
    t = _tl_norm_v2(text)
    return any(tok in t for tok in tokens)


def _tl_item_text_v2(item, post):
    parts = []
    for attr in ("title", "text", "body", "raw_text", "summary", "source_name"):
        try:
            value = getattr(item, attr, "")
        except Exception:
            value = ""
        if value:
            parts.append(str(value))
    try:
        if isinstance(post, dict):
            parts.append(str(post.get("text") or ""))
    except Exception:
        pass
    return "\n".join(parts)


def _tl_category_v2(item, post):
    hay = _tl_item_text_v2(item, post)

    red_terms = (
        "штраф", "фнс", "налог", "самозанят", "проверка", "проверки",
        "блокиров", "замороз", "приостанов", "приостановка выплат",
        "выплат", "оферт", "закон вступ", "вступит в силу", "дедлайн",
        "срок до", "обязател", "маркиров", "честный знак", "суд",
        "ответственность", "нарушен", "санкц", "риск штраф",
    )

    green_terms = (
        "хорошая новость", "расширил", "расширила", "добавил", "добавила",
        "запустил", "запустила", "открыл", "открыла", "упростил", "упростила",
        "снизил", "снизила", "компенсац", "вернет", "вернут", "новая возможность",
        "партнеры ozon", "партнёры ozon", "realfbs", "real fbs", "comfort",
        "express", "экспресс-достав", "экспресс достав", "новые города",
        "добавил метод", "добавила метод",
    )

    blue_terms = (
        "аналитик", "исследован", "статистик", "рынок", "тренд", "динамик",
        "индекс", "итоги", "рейтинг", "отчет", "отчёт", "data insight",
        "e-commerce", "ecommerce", "маркетплейсов стало", "селлеры все чаще",
        "селлеры всё чаще", "стратег", "наблюден", "доли рынка",
    )

    orange_terms = (
        "логистик", "доставк", "склад", "пвз", "карточк", "продвижен",
        "реклам", "условия", "правила", "изменил", "изменила", "обновил",
        "обновила", "жалоб", "госуслуг", "роспотребнадзор", "минцифры",
        "спор", "возврат", "сортиров", "измерять товары",
    )

    event_or_leadgen = (
        "вебинар", "круглый стол", "регистрация", "22 мая", "13:00",
        "эфир", "конференц", "неделе российского ритейла", "лидоген",
    )

    # Risk wins first.
    if _tl_any_v2(hay, red_terms):
        return "🔴 Важно", "🔴"

    # Positive marketplace capability: green, but not if it is just an event promo.
    if _tl_any_v2(hay, green_terms) and not _tl_any_v2(hay, event_or_leadgen):
        return "🟢 Хорошая новость", "🟢"

    # Research/market observations: blue, unless there is an operational/regulatory change.
    if _tl_any_v2(hay, blue_terms) and not _tl_any_v2(hay, red_terms):
        return "🔵 Интересно / аналитика", "🔵"

    if _tl_any_v2(hay, orange_terms):
        return "🟠 Обратите внимание", "🟠"

    return "", ""


def _tl_takeaway_v2(item, post, category_label):
    hay = _tl_item_text_v2(item, post)

    if _tl_any_v2(hay, ("realfbs", "real fbs", "comfort", "express", "партнеры ozon", "партнёры ozon", "экспресс-достав", "экспресс достав")):
        return (
            "Вывод для селлера:\n"
            "Если вы работаете по realFBS Express или Comfort, проверьте доступность метода «Партнёры Ozon» "
            "в своих городах. Это может повлиять на сроки доставки, нагрузку на сборку и экономику заказов."
        )

    if _tl_any_v2(hay, ("доставк", "логистик", "склад", "пвз", "сортиров", "измерять товары")):
        return (
            "Вывод для селлера:\n"
            "Проверьте, влияет ли изменение на вашу схему хранения, сборки и доставки. "
            "Если да — пересчитайте сроки, операционные затраты и возможные узкие места."
        )

    if _tl_any_v2(hay, ("штраф", "фнс", "налог", "самозанят", "блокиров", "приостанов", "выплат", "оферт", "закон", "маркиров", "честный знак")):
        return (
            "Вывод для селлера:\n"
            "Это зона риска. Проверьте документы, выплаты, маркировку, договоры и процессы, "
            "которые могут попасть под новые требования или проверки."
        )

    if _tl_any_v2(hay, ("жалоб", "госуслуг", "роспотребнадзор", "минцифры", "спор", "потребител")):
        return (
            "Вывод для селлера:\n"
            "Держите в порядке переписку, статусы заказов, документы по качеству товара и возвратам. "
            "Если спор уйдёт в электронную жалобу, доказательства понадобятся быстро."
        )

    if _tl_any_v2(hay, ("аналитик", "исследован", "статистик", "рынок", "тренд", "динамик", "индекс", "data insight", "селлеры все чаще", "селлеры всё чаще")):
        return (
            "Вывод для селлера:\n"
            "Это не срочная инструкция, а рыночный сигнал. Используйте его для проверки стратегии: "
            "каналы продаж, маржа, зависимость от одной площадки и планы на сезон."
        )

    if category_label == "🟢 Хорошая новость":
        return (
            "Вывод для селлера:\n"
            "Проверьте, можно ли использовать новую возможность в вашей модели продаж. "
            "Если она подходит — пересчитайте экономику и протестируйте на ограниченном объёме."
        )

    if category_label == "🔵 Интересно / аналитика":
        return (
            "Вывод для селлера:\n"
            "Это повод сверить свою стратегию с рынком: ассортимент, каналы продаж, маржинальность и зависимость от площадок."
        )

    if category_label == "🔴 Важно":
        return (
            "Вывод для селлера:\n"
            "Проверьте, есть ли прямой риск для ваших денег, документов, карточек, выплат или соблюдения правил площадки."
        )

    return (
        "Вывод для селлера:\n"
        "Проверьте, есть ли практическое влияние на ваши товары, карточки, логистику, выплаты или маржу."
    )


def _tl_replace_takeaway_v2(text, takeaway):
    import re
    text = str(text or "")

    patterns = [
        r"Вывод для селлера:\s*\n\s*Что важно селлеру:\s*проверьте, затрагивает ли изменение ваши товары и процессы\.?",
        r"Вывод для селлера:\s*\n\s*Проверьте, затрагивает ли изменение ваши товары и процессы\.?",
        r"Что важно селлеру:\s*проверьте, затрагивает ли изменение ваши товары и процессы\.?",
    ]
    for pat in patterns:
        if re.search(pat, text, flags=re.IGNORECASE):
            return re.sub(pat, takeaway, text, count=1, flags=re.IGNORECASE)

    # If no takeaway exists, insert before category/source.
    marker_match = re.search(r"\n\n[🔴🟠🟢🔵] .+?(?=\n\nИсточник:|\Z)", text)
    if marker_match:
        pos = marker_match.start()
        return text[:pos].rstrip() + "\n\n" + takeaway + "\n" + text[pos:]
    return text.rstrip() + "\n\n" + takeaway


def _tl_replace_category_v2(text, category_label):
    import re
    text = str(text or "")

    labels = (
        "🔴 Важно",
        "🟠 Обратите внимание",
        "🟢 Хорошая новость",
        "🔵 Интересно / аналитика",
    )

    # Remove standalone old category labels.
    lines = []
    for line in text.splitlines():
        if line.strip() in labels:
            continue
        lines.append(line)
    text = "\n".join(lines).rstrip()

    # Insert category before source if possible.
    source_marker = "\n\nИсточник:"
    if source_marker in text:
        head, tail = text.split(source_marker, 1)
        return head.rstrip() + "\n\n" + category_label + source_marker + tail

    return text.rstrip() + "\n\n" + category_label


def _tl_trim_duplicate_title_v2(text):
    import re
    text = str(text or "")

    m = re.match(r"(?s)^\s*<b>(.*?)</b>\s*\n\n(.*)$", text)
    if not m:
        return text

    title = re.sub(r"<.*?>", "", m.group(1)).strip()
    rest = m.group(2)

    if not title:
        return text

    # If body starts with the title, remove duplicate once.
    title_plain = re.sub(r"\s+", " ", title).strip()
    rest_plain_start = re.sub(r"\s+", " ", rest[: len(title_plain) + 80]).strip()

    if rest_plain_start.lower().replace("ё", "е").startswith(title_plain.lower().replace("ё", "е")):
        rest = rest[len(title_plain):].lstrip(" .—-:;")
        return f"<b>{title}</b>\n\n{rest}"

    return text


def build_post(item, seller_result=None):  # type: ignore[override]
    post = _BUILD_POST_BEFORE_TRAFFIC_LIGHT_TAKEAWAYS_V2(item, seller_result)

    try:
        category_label, category_indicator = _tl_category_v2(item, post)
        if not category_label:
            category_label = post.get("category_label") or ""
            category_indicator = post.get("category_indicator") or ""

        if category_label:
            post["category_label"] = category_label
            post["category_indicator"] = category_indicator

        text = post.get("text") or ""
        text = _tl_trim_duplicate_title_v2(text)

        if category_label:
            takeaway = _tl_takeaway_v2(item, post, category_label)
            text = _tl_replace_takeaway_v2(text, takeaway)
            text = _tl_replace_category_v2(text, category_label)

        post["text"] = text
    except Exception:
        # Never break publishing because of editorial post-processing.
        return post

    return post
# --- END PRODUCTION HOTFIX: traffic-light category and seller takeaway v2 ---

# --- PRODUCTION HOTFIX: traffic-light final repair v3 ---
# Repairs:
# - allow useful green logistics/delivery opportunities as regular posts;
# - keep event/leadgen candidates denied;
# - repair posts where body was trimmed too aggressively;
# - shorten known ugly titles.
try:
    _BUILD_POST_BEFORE_TRAFFIC_LIGHT_FINAL_REPAIR_V3 = build_post
except NameError:
    _BUILD_POST_BEFORE_TRAFFIC_LIGHT_FINAL_REPAIR_V3 = None


def _tl3_norm(value):
    return str(value or "").lower().replace("ё", "е")


def _tl3_any(text, tokens):
    t = _tl3_norm(text)
    return any(tok in t for tok in tokens)


def _tl3_item_full_text(item):
    parts = []
    for attr in ("title", "text", "body", "raw_text", "summary", "source_name"):
        try:
            value = getattr(item, attr, "")
        except Exception:
            value = ""
        if value:
            parts.append(str(value))
    return "\n".join(parts)


def _tl3_clean_body_from_item(item, max_chars=850):
    import re

    title = ""
    try:
        title = str(getattr(item, "title", "") or "")
    except Exception:
        title = ""

    body = ""
    for attr in ("text", "body", "raw_text", "summary"):
        try:
            value = str(getattr(item, attr, "") or "")
        except Exception:
            value = ""
        if len(value) > len(body):
            body = value

    body = re.sub(r"https?://\S+|t\.me/\S+", "", body)
    body = re.sub(r"\s+", " ", body).strip()

    # Remove duplicated title prefix, but do not nuke the whole body.
    if title:
        title_clean = re.sub(r"\s+", " ", title).strip()
        if len(title_clean) > 30 and body.lower().replace("ё", "е").startswith(title_clean[:120].lower().replace("ё", "е")):
            body = body[len(title_clean):].lstrip(" .—-:;")

    # Known duplicated first sentence cleanup.
    body = re.sub(
        r"^Ozon расширил партн[её]рскую экспресс-доставку ещё на 11 городов\s*",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(r"\s+", " ", body).strip()

    if len(body) > max_chars:
        body = body[:max_chars].rsplit(" ", 1)[0].rstrip(" .,;:") + "..."

    return body


def _tl3_short_title(item, fallback_title=""):
    hay = _tl3_item_full_text(item)

    if _tl3_any(hay, ("ozon", "realfbs", "real fbs", "express", "comfort", "партнеры ozon", "партнёры ozon")) and _tl3_any(hay, ("11 город", "новые города", "экспресс-достав")):
        return "Ozon расширил экспресс-доставку realFBS ещё на 11 городов"

    if _tl3_any(hay, ("госуслуг", "электронную книгу жалоб", "жаловаться на маркетплейсы")):
        return "На Госуслугах появится книга жалоб на маркетплейсы"

    return fallback_title


def _tl3_is_green_delivery(item):
    hay = _tl3_item_full_text(item)
    return (
        _tl3_any(hay, ("ozon", "wildberries", "wb", "яндекс маркет"))
        and _tl3_any(hay, ("расширил", "расширила", "добавил", "добавила", "запустил", "запустила"))
        and _tl3_any(hay, ("доставк", "realfbs", "real fbs", "express", "comfort", "партнеры ozon", "партнёры ozon", "пвз", "склад", "город"))
        and not _tl3_is_event_leadgen(item)
    )


def _tl3_is_event_leadgen(item):
    hay = _tl3_item_full_text(item)
    return _tl3_any(
        hay,
        (
            "круглый стол",
            "вебинар",
            "эфир",
            "регистрация",
            "неделе российского ритейла",
            "22 мая",
            "13:00",
            "мск",
            "лидоген",
            "лид-магнит",
            "мастер-класс",
            "конференц",
        ),
    )


def _tl3_rebuild_text(item, post, category_label):
    import re

    old_text = str(post.get("text") or "")

    old_title = ""
    m = re.search(r"<b>(.*?)</b>", old_text, flags=re.DOTALL)
    if m:
        old_title = re.sub(r"<.*?>", "", m.group(1)).strip()

    title = _tl3_short_title(item, old_title)
    if not title:
        title = old_title

    body = _tl3_clean_body_from_item(item)

    takeaway = ""
    m2 = re.search(r"Вывод для селлера:\s*\n.*?(?=\n\n[🔴🟠🟢🔵] |\n\nИсточник:|\Z)", old_text, flags=re.DOTALL)
    if m2:
        takeaway = m2.group(0).strip()

    if not takeaway:
        takeaway = "Вывод для селлера:\nПроверьте, есть ли практическое влияние на ваши товары, логистику, выплаты или маржу."

    source = ""
    # Preserve V3 source-link contract expected by read-more tests.
    m3 = re.search(r"Ссылка на источник:\s*https?://\S+", old_text)
    if m3:
        source = m3.group(0).strip()
    else:
        m3 = re.search(r"Источник:\s*.*", old_text)
        if m3:
            source = m3.group(0).strip()

    parts = []
    if title:
        parts.append(f"<b>{title}</b>")
    if body:
        parts.append(body)
    parts.append(takeaway)
    if category_label:
        parts.append(category_label)
    if source:
        parts.append(source)

    text = "\n\n".join(parts).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def build_post(item, seller_result=None):  # type: ignore[override]
    post = _BUILD_POST_BEFORE_TRAFFIC_LIGHT_FINAL_REPAIR_V3(item, seller_result)

    try:
        if _tl3_is_event_leadgen(item):
            post["regular_allowed"] = False
            post["regular_denial_reason"] = "native_ad_leadgen"
            # Keep category text if useful for digest, but do not allow regular.
            if not post.get("category_label"):
                post["category_label"] = "🔵 Интересно / аналитика"
                post["category_indicator"] = "🔵"
            return post

        if _tl3_is_green_delivery(item):
            post["category_label"] = "🟢 Хорошая новость"
            post["category_indicator"] = "🟢"
            post["regular_allowed"] = True
            post["regular_denial_reason"] = ""
            post["text"] = _tl3_rebuild_text(item, post, "🟢 Хорошая новость")
            return post

        # For non-green posts: repair empty/over-trimmed body only when text is too short.
        text = str(post.get("text") or "")
        if len(text) < 650 and post.get("category_label"):
            post["text"] = _tl3_rebuild_text(item, post, post.get("category_label") or "")
    except Exception:
        return post

    return post
# --- END PRODUCTION HOTFIX: traffic-light final repair v3 ---

# --- PRODUCTION HOTFIX: Ozon realFBS body/source repair v4 ---
try:
    _BUILD_POST_BEFORE_OZON_REALFBS_REPAIR_V4 = build_post
except NameError:
    _BUILD_POST_BEFORE_OZON_REALFBS_REPAIR_V4 = None


def _tl4_get_item_text(item):
    parts = []
    for attr in ("text", "body", "raw_text", "summary", "title"):
        try:
            v = getattr(item, attr, "")
        except Exception:
            v = ""
        if v:
            parts.append(str(v))
    return "\n".join(parts)


def _tl4_source_link(item):
    try:
        link = getattr(item, "link", "") or getattr(item, "url", "")
    except Exception:
        link = ""
    return str(link or "").strip()


def _tl4_ozon_realfbs_body(item):
    import re
    raw = _tl4_get_item_text(item)
    raw = re.sub(r"https?://\S+|t\.me/\S+", "", raw)
    raw = re.sub(r"\s+", " ", raw).strip()

    if not raw:
        return ""

    # Start from real content, not from sliced title.
    starts = [
        "Ozon добавил метод",
        "Ozon добавила метод",
        "Новые города:",
        "Владимир, Ижевск",
    ]
    start_pos = -1
    for marker in starts:
        pos = raw.lower().replace("ё", "е").find(marker.lower().replace("ё", "е"))
        if pos >= 0:
            start_pos = pos
            break

    if start_pos >= 0:
        raw = raw[start_pos:].strip()

    raw = raw.replace("Если у вас плохо прогружаются файлы, все посты также доступны в MAX", "").strip()

    # Make first sentence human if raw starts with method.
    raw = re.sub(
        r"^Ozon добавил метод «Партнёры Ozon» ещё в 11 городах:",
        "Ozon добавил метод «Партнёры Ozon» ещё в 11 городах:",
        raw,
        flags=re.IGNORECASE,
    )

    if len(raw) > 900:
        raw = raw[:1600].rsplit(" ", 1)[0].rstrip(" .,;:") + "..."

    return raw


def build_post(item, seller_result=None):  # type: ignore[override]
    post = _BUILD_POST_BEFORE_OZON_REALFBS_REPAIR_V4(item, seller_result)

    try:
        text = str(post.get("text") or "")
        hay = _tl4_get_item_text(item).lower().replace("ё", "е")

        is_ozon_realfbs = (
            "ozon" in hay
            and ("realfbs" in hay or "real fbs" in hay)
            and ("партнеры ozon" in hay or "партнёры ozon" in hay or "экспресс-достав" in hay)
        )

        if is_ozon_realfbs:
            import re

            title = "Ozon расширил экспресс-доставку realFBS ещё на 11 городов"
            body = _tl4_ozon_realfbs_body(item)

            takeaway = (
                "Вывод для селлера:\n"
                "Если вы работаете по realFBS Express или Comfort, проверьте доступность метода «Партнёры Ozon» "
                "в своих городах. Это может повлиять на сроки доставки, нагрузку на сборку и экономику заказов."
            )

            link = _tl4_source_link(item)
            source_line = f"Ссылка на источник: {link}" if link else ""

            parts = [
                f"<b>{title}</b>",
                body,
                takeaway,
                "🟢 Хорошая новость",
                source_line,
            ]
            post["text"] = "\n\n".join([p for p in parts if p]).strip()
            post["category_label"] = "🟢 Хорошая новость"
            post["category_indicator"] = "🟢"
            post["regular_allowed"] = True
            post["regular_denial_reason"] = ""
            return post

        # Preserve source URL contract for all repaired posts when link exists.
        link = _tl4_source_link(item)
        if link and "Ссылка на источник:" not in text:
            text = re.sub(r"\n\nИсточник:\s*.*$", "", text, flags=re.DOTALL)
            text = text.rstrip() + f"\n\nСсылка на источник: {link}"
            post["text"] = text
    except Exception:
        return post

    return post
# --- END PRODUCTION HOTFIX: Ozon realFBS body/source repair v4 ---

# --- PRODUCTION HOTFIX: preserve plain source URL contract v5 ---
try:
    _BUILD_POST_BEFORE_SOURCE_CONTRACT_V5 = build_post
except NameError:
    _BUILD_POST_BEFORE_SOURCE_CONTRACT_V5 = None


def _source_contract_v5_get_url(item, post):
    for key in ("source_url", "url", "link"):
        try:
            value = post.get(key) if isinstance(post, dict) else ""
        except Exception:
            value = ""
        if value and str(value).startswith(("http://", "https://")):
            return str(value).strip()

    for attr in ("source_url", "url", "link"):
        try:
            value = getattr(item, attr, "")
        except Exception:
            value = ""
        if value and str(value).startswith(("http://", "https://")):
            return str(value).strip()

    return ""


def build_post(item, seller_result=None):  # type: ignore[override]
    post = _BUILD_POST_BEFORE_SOURCE_CONTRACT_V5(item, seller_result)

    try:
        import re

        text = str(post.get("text") or "")
        url = _source_contract_v5_get_url(item, post)

        if url:
            # Remove broken/generated source lines and restore required plain URL contract.
            text = re.sub(r"\n\nИсточник:\s*.*$", "", text, flags=re.DOTALL).rstrip()
            text = re.sub(r"\n\nСсылка на источник:\s*https?://\S+\s*$", "", text, flags=re.DOTALL).rstrip()
            text = text + f"\n\nСсылка на источник: {url}"
            post["text"] = text
            post["source_link_present"] = True
    except Exception:
        return post

    return post
# --- END PRODUCTION HOTFIX: preserve plain source URL contract v5 ---

# --- PRODUCTION HOTFIX: V3 LLM editor contract v6 ---
try:
    _BUILD_POST_BEFORE_LLM_EDITOR_CONTRACT_V6 = build_post
except NameError:
    _BUILD_POST_BEFORE_LLM_EDITOR_CONTRACT_V6 = None


def _v3_editor_clean_fragment_v6(text):
    import re

    text = str(text or "")
    text = re.sub(r"(?is)<[^>]+>", "", text)
    text = text.replace("```json", "").replace("```", "")
    text = text.replace("🎯", "")

    # Drop bridge/runtime metadata. This is not post body.
    text = re.sub(
        r"(?im)^\s*(Площадка|Типы сигналов|Уровни|Источник|Дата источника|source|levels|signal_types)\s*[:：].*$",
        "",
        text,
    )

    # Drop LLM diagnostics if ever leaked.
    text = re.sub(
        r"(?im)^\s*(llm_[a-z_]+|summary_mode|prompt_type|production_mutation|queue_mutation|live_send)\s*=.*$",
        "",
        text,
    )
    text = re.sub(r"(?im)^\s*LLM\s*:.*$", "", text)

    # Formatter owns labels.
    text = re.sub(r"^\s*(Кратко|Summary)\s*[:：]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"^\s*(Вывод для селлера|Что это значит для селлера|Seller conclusion)\s*[:：]\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _v3_editor_safe_title_v6(item, seller_result=None, old_text=""):
    import re

    seller_result = seller_result or {}

    # Model title can be added later; for now this supports it if router returns it.
    title = (
        seller_result.get("title_suggestion")
        or seller_result.get("title")
        or getattr(item, "title", "")
        or ""
    )
    title = _v3_editor_clean_fragment_v6(title)

    if not title:
        m = re.search(r"<b>(.*?)</b>", str(old_text or ""), flags=re.DOTALL)
        if m:
            title = _v3_editor_clean_fragment_v6(m.group(1))

    title = re.sub(r"https?://\S+|t\.me/\S+", "", title).strip()
    title = title.strip(" -–—|:;")

    # Do NOT cut to first sentence. That was the bug.
    limit = 150
    if len(title) <= limit:
        return title

    cut = title[: limit + 1]
    candidates = []

    for sep in (" — ", " – ", ": ", "; ", " | ", " / "):
        pos = cut.rfind(sep)
        if pos >= 70:
            candidates.append(pos)

    # Prefer sentence boundary only if it does not leave a stupid stub.
    pos = cut.rfind(". ")
    if pos >= 95:
        candidates.append(pos)

    for sep in (", ", " "):
        pos = cut.rfind(sep)
        if pos >= 105:
            candidates.append(pos)

    if candidates:
        title = cut[: max(candidates)].strip()
    else:
        title = cut[:limit].strip()

    title = title.rstrip(" .,—-:;")
    return title + "…"


def _v3_editor_body_from_old_v6(old_text):
    import re

    text = str(old_text or "")

    # Remove title.
    text = re.sub(r"(?s)^\s*<b>.*?</b>\s*", "", text).strip()

    # Remove old seller conclusion and source/category tail.
    text = re.sub(r"(?s)\n*\s*Вывод для селлера:\s*.*?(?=\n\n[🔴🟠🟢🔵] |\n\nИсточник:|\n\nСсылка на источник:|\Z)", "", text)
    text = re.sub(r"(?s)\n\n[🔴🟠🟢🔵] .*?(?=\n\nИсточник:|\n\nСсылка на источник:|\Z)", "", text)
    text = re.sub(r"(?s)\n\nИсточник:\s*.*$", "", text)
    text = re.sub(r"(?s)\n\nСсылка на источник:\s*https?://\S+\s*$", "", text)

    return _v3_editor_clean_fragment_v6(text)


def _v3_editor_extract_category_line_v6(post):
    import re

    text = str((post or {}).get("text") or "")
    m = re.search(r"\n\n([🔴🟠🟢🔵] [^\n]+)", text)
    if m:
        return m.group(1).strip()

    label = str((post or {}).get("category_label") or "").strip()
    return label


def _v3_editor_source_line_v6(item, post):
    for key in ("source_url", "url", "link"):
        try:
            value = post.get(key) if isinstance(post, dict) else ""
        except Exception:
            value = ""
        if value and str(value).startswith(("http://", "https://")):
            return f"Ссылка на источник: {str(value).strip()}"

    for attr in ("source_url", "url", "link"):
        try:
            value = getattr(item, attr, "")
        except Exception:
            value = ""
        if value and str(value).startswith(("http://", "https://")):
            return f"Ссылка на источник: {str(value).strip()}"

    return ""


def build_post(item, seller_result=None):  # type: ignore[override]
    post = _BUILD_POST_BEFORE_LLM_EDITOR_CONTRACT_V6(item, seller_result)

    try:
        seller_result = seller_result or {}
        old_text = str(post.get("text") or "")

        title = _v3_editor_safe_title_v6(item, seller_result, old_text=old_text)

        model_summary = _v3_editor_clean_fragment_v6(seller_result.get("summary") or "")
        model_conclusion = _v3_editor_clean_fragment_v6(seller_result.get("seller_conclusion") or "")

        body = model_summary or _v3_editor_body_from_old_v6(old_text)

        if not model_conclusion:
            model_conclusion = (
                "Проверьте, есть ли практическое влияние на ваши товары, логистику, выплаты или маржу."
            )

        category_line = _v3_editor_extract_category_line_v6(post)
        source_line = _v3_editor_source_line_v6(item, post)

        parts = []
        if title:
            parts.append(f"<b>{title}</b>")
        if body:
            parts.append(body)
        if model_conclusion:
            parts.append("🎯 Что это значит для селлера:\n" + model_conclusion)
        if category_line:
            parts.append(category_line)
        if source_line:
            parts.append(source_line)

        post["text"] = "\n\n".join([p for p in parts if p]).strip()
        return post
    except Exception:
        return post
# --- END PRODUCTION HOTFIX: V3 LLM editor contract v6 ---
