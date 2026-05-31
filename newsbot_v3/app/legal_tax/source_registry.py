from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

_ALLOWED_SOURCE_TYPES = {"legal_api", "tax_official", "marking_official", "regulator_official", "marketplace_docs"}
_ALLOWED_TRUST_LEVELS = {"official", "high", "medium"}
_ALLOWED_ACCESS_MODES = {"api_readonly", "opendata", "rss", "html", "pdf", "manual_registry"}
_ALLOWED_IMPLEMENTATION_STATUSES = {"planned", "dry_run_ready", "manual_only"}


@dataclass(frozen=True)
class LegalTaxSource:
    source_id: str
    title: str
    source_type: str
    trust_level: str
    access_mode: str
    enabled_default: bool
    requires_credentials: bool
    credentials_env_keys: list[str]
    topics: list[str]
    seller_use: str
    safety_notes: str
    implementation_status: str
    locator: str
    notes: str = ""



def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "legal_tax_sources.json"


def load_legal_tax_sources(config_path: str | Path | None = None) -> list[LegalTaxSource]:
    cfg_path = Path(config_path) if config_path else _default_config_path()
    records = json.loads(cfg_path.read_text(encoding="utf-8"))
    return [LegalTaxSource(**record) for record in records]


def validate_legal_tax_sources(sources: Sequence[LegalTaxSource]) -> dict[str, object]:
    errors: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if source.source_id in seen:
            errors.append(f"duplicate source_id: {source.source_id}")
        seen.add(source.source_id)
        if source.source_type not in _ALLOWED_SOURCE_TYPES:
            errors.append(f"{source.source_id}: invalid source_type={source.source_type}")
        if source.trust_level not in _ALLOWED_TRUST_LEVELS:
            errors.append(f"{source.source_id}: invalid trust_level={source.trust_level}")
        if source.access_mode not in _ALLOWED_ACCESS_MODES:
            errors.append(f"{source.source_id}: invalid access_mode={source.access_mode}")
        if source.implementation_status not in _ALLOWED_IMPLEMENTATION_STATUSES:
            errors.append(f"{source.source_id}: invalid implementation_status={source.implementation_status}")
        if source.requires_credentials and not source.credentials_env_keys:
            errors.append(f"{source.source_id}: requires_credentials=true but credentials_env_keys is empty")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "count": len(sources),
    }


def summarize_sources(sources: Sequence[LegalTaxSource]) -> dict[str, int]:
    summary: dict[str, int] = {
        "sources_seen": len(sources),
        "official_sources_seen": sum(1 for item in sources if item.trust_level == "official"),
        "requires_credentials_count": sum(1 for item in sources if item.requires_credentials),
        "enabled_default_count": sum(1 for item in sources if item.enabled_default),
    }
    return summary


def get_enabled_sources(sources: Sequence[LegalTaxSource]) -> list[LegalTaxSource]:
    return [source for source in sources if source.enabled_default]


def detect_missing_credentials(source: LegalTaxSource, env: Mapping[str, str] = os.environ) -> list[str]:
    if not source.requires_credentials:
        return []
    missing: list[str] = []
    for key in source.credentials_env_keys:
        if not env.get(key):
            missing.append(key)
    return missing
