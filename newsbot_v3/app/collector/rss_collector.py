from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RSSSourceHealth:
    source: str
    url: str
    status: str
    message: str


def load_v2_rss_sources(v2_inventory: dict[str, Any] | None = None) -> list[dict[str, str]]:
    count = int((v2_inventory or {}).get("rss_sources", 0))
    return [{"source": f"v2_rss_{i+1}", "url": f"mock://rss/{i+1}"} for i in range(count)]


def dry_run_rss(v2_inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    sources = load_v2_rss_sources(v2_inventory)
    health = [RSSSourceHealth(s["source"], s["url"], "OK", "dry-run mock fetch").__dict__ for s in sources]
    for h in health:
        print(f"RSS_SOURCE_HEALTH source={h['source']} status={h['status']} message={h['message']}")
    return {"collector": "rss", "dry_run": True, "sources": len(sources), "items": 0, "health": health}
