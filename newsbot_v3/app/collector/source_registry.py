from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SourceRecord:
    source_id: str
    source_type: str
    marketplace: str
    trust_level: str
    rag_layer: str
    locator: str
    enabled: bool = True
    last_seen: str | None = None
    error_count: int = 0
    notes: str = ""


@dataclass
class SourceRegistry:
    sources: list[SourceRecord] = field(default_factory=list)

    def add(self, record: SourceRecord) -> None:
        self.sources.append(record)

    def snapshot(self) -> dict:
        return {"status": "OK", "sources": [s.__dict__ for s in self.sources], "updated_at": datetime.now(timezone.utc).isoformat()}


def source_registry_snapshot() -> dict:
    return SourceRegistry().snapshot()
