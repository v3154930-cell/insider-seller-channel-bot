from __future__ import annotations

import json
import os
from pathlib import Path


def visuals_enabled() -> bool:
    return os.getenv("NEWSBOT_V3_ENABLE_MASCOT_IMAGES", "false").lower() == "true"


def _manifest_path() -> Path:
    return Path(__file__).resolve().parents[2] / "assets" / "mascot" / "manifest.json"


def load_manifest() -> dict:
    path = _manifest_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _tagged(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def select_mascot_kind(post_kind: str = "regular", tags: list[str] | None = None, title: str = "", text: str = "", source: str = "", digest_kind: str = "", audio_digest_kind: str = "") -> str:
    if post_kind == "audio" or audio_digest_kind:
        return "audio_digest"
    if post_kind == "digest":
        dk = (digest_kind or "").lower()
        return "morning_digest" if dk == "morning" else "evening_digest"

    hay = " ".join((tags or []) + [title, text, source]).lower().replace("ё", "е")
    if _tagged(hay, ("important", "urgent", "alert", "важн", "сроч")):
        return "urgent_important"
    if _tagged(hay, ("analytics", "analysis", "аналит", "market analysis")):
        return "analytics"
    if _tagged(hay, ("law", "tax", "legal", "regulation", "закон", "налог", "регуля")):
        return "law_taxes"
    if _tagged(hay, ("marking", "compliance", "честный знак", "маркиров")):
        return "marking_compliance"
    if _tagged(hay, ("money", "profit", "tariff", "commission", "payout", "деньг", "прибыл", "тариф", "комисс", "выплат")):
        return "money_profit"
    if _tagged(hay, ("interesting", "интерес")):
        return "interesting_news"
    return "base_friendly"


def select_mascot_asset(**kwargs) -> tuple[str, str]:
    kind = select_mascot_kind(**kwargs)
    manifest = load_manifest()
    entry = manifest.get(kind) or {}
    selected = entry.get("web_path") or entry.get("mobile_path") or entry.get("source_path") or ""
    if selected:
        selected = str((_manifest_path().parent / selected).resolve())
    return kind, selected
