from __future__ import annotations

import os
from typing import Any


def load_tg_json_urls(env: dict[str, str] | None = None) -> list[str]:
    env = env or os.environ
    raw = env.get("TG_JSON_URLS", "")
    return [x.strip() for x in raw.split(",") if x.strip()]


def dry_run_telegram(env: dict[str, str] | None = None, mock_fetch: bool = True) -> dict[str, Any]:
    urls = load_tg_json_urls(env)
    per_source = [{"url": u, "status": "OK" if mock_fetch else "SKIPPED", "items": 0} for u in urls]
    return {"collector": "telegram", "dry_run": True, "mock_fetch": mock_fetch, "sources": len(urls), "items": 0, "health": per_source}
