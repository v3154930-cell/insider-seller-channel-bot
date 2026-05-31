from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class MediaPlan:
    image_present: bool
    image_source: str
    image_url: str | None
    image_path: str | None
    placeholder_category: str | None
    image_attach_attempted: bool
    image_required: bool
    fallback_reason: str
    diagnostics_json: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _placeholder_config() -> dict[str, str]:
    cfg = _repo_root() / "config" / "image_placeholders.json"
    if not cfg.exists():
        return {}
    return json.loads(cfg.read_text(encoding="utf-8"))


def _valid_external_url(url: str | None) -> bool:
    if not url:
        return False
    p = urlparse(url.strip())
    return p.scheme in {"http", "https"} and bool(p.netloc)


def extract_candidate_image(item) -> str | None:
    for field in ("image_url", "media_url", "picture", "thumbnail"):
        value = getattr(item, field, None)
        if _valid_external_url(value):
            return value.strip()
    return None


def classify_placeholder_topic(item, topic_tags=None, marketplace=None) -> str:
    tags = [str(t).lower() for t in (topic_tags or []) if t]
    title = (getattr(item, "title", "") or "").lower()
    text = (getattr(item, "text", "") or "").lower()
    source = (getattr(item, "source_name", "") or "").lower()
    mp = (marketplace or source or "").lower()

    hay = " ".join(tags + [title, text, mp])
    if any(k in hay for k in ("legal", "налог", "tax", "ндс", "закон", "регуля")):
        return "legal_tax"
    if any(k in hay for k in ("честный знак", "marking", "маркиров")):
        return "marking_chestny_znak"
    if any(k in hay for k in ("logistics", "доставка", "склад", "fulfillment", "фулфил")):
        return "logistics"
    if any(k in hay for k in ("finance", "payment", "платеж", "эквайр", "комисс")):
        return "finance_payments"
    if any(k in hay for k in ("ads", "promo", "реклама", "продвиж")):
        return "ads_promotion"
    if any(k in hay for k in ("certificate", "сертифик", "документ", "декларац")):
        return "documents_certification"
    if "wb" in hay or "wildberries" in hay:
        return "wb"
    if "ozon" in hay:
        return "ozon"
    if "yandex market" in hay or "яндекс маркет" in hay:
        return "yandex_market"
    return "generic_marketplace"


def resolve_image_for_post(item, topic_tags=None, marketplace=None) -> MediaPlan:
    external = extract_candidate_image(item)
    diag = {"external_candidate": external, "placeholder_config_loaded": False}
    if external:
        plan = MediaPlan(True, "external", external, None, None, False, False, "", "")
        plan.diagnostics_json = json.dumps({**diag, "resolution": "external"}, ensure_ascii=False)
        return plan

    category = classify_placeholder_topic(item, topic_tags=topic_tags, marketplace=marketplace)
    config = _placeholder_config()
    diag["placeholder_config_loaded"] = bool(config)
    rel_path = config.get(category) or config.get("generic_marketplace")
    if rel_path:
        abs_path = _repo_root() / rel_path
        if abs_path.exists():
            plan = MediaPlan(True, "placeholder", None, str(abs_path), category, False, False, "", "")
            plan.diagnostics_json = json.dumps({**diag, "resolution": "placeholder", "category": category}, ensure_ascii=False)
            return plan

    fallback = "placeholder_missing" if rel_path else "placeholder_unconfigured"
    plan = MediaPlan(False, "none", None, None, category, False, False, fallback, "")
    plan.diagnostics_json = json.dumps({**diag, "resolution": "none", "fallback_reason": fallback}, ensure_ascii=False)
    return plan


def validate_media_plan(plan: MediaPlan) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if plan.image_source not in {"external", "placeholder", "none"}:
        errors.append("invalid_image_source")
    if plan.image_required:
        errors.append("image_required_must_be_false")
    if plan.image_source == "external" and not _valid_external_url(plan.image_url):
        errors.append("invalid_external_url")
    if plan.image_source == "placeholder" and (not plan.image_path or not Path(plan.image_path).exists()):
        errors.append("missing_placeholder_file")
    if plan.image_source == "none" and plan.image_present:
        errors.append("none_source_cannot_be_present")
    return (len(errors) == 0, errors)


def media_plan_to_dict(plan: MediaPlan) -> dict:
    return asdict(plan)
