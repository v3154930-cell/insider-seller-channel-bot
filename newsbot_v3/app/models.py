from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class NewsItem:
    news_id: str
    title: str
    text: str
    link: Optional[str] = None
    source_name: str = "unknown"
    marketplace: Optional[str] = None
    importance: str = "🟡"


@dataclass
class RawNews:
    external_id: str
    source: str
    title: str
    body: str
    link: Optional[str] = None
    published_at: Optional[str] = None
    content_hash: Optional[str] = None
    raw_payload: Optional[str] = None


@dataclass
class NormalizedNews:
    raw_news_external_id: str
    normalized_id: str
    title: str
    body: str
    source: str
    link: Optional[str] = None
    language: Optional[str] = None


@dataclass
class ScoredNews:
    normalized_id: str
    score: float
    importance: str
    reasons: Optional[str] = None


@dataclass
class PublishCandidate:
    normalized_id: str
    candidate_id: str
    short_post_text: str
    source_link: Optional[str] = None
    is_digest_candidate: bool = False


@dataclass
class PublishedMessage:
    candidate_id: str
    message_id: Optional[int]
    channel: str
    published_at: Optional[str]
    status: str


@dataclass
class FullArticle:
    normalized_id: str
    full_text: str
    source_link: Optional[str] = None
    fetched_at: Optional[str] = None


@dataclass
class DigestRun:
    digest_id: str
    run_started_at: Optional[str]
    run_finished_at: Optional[str]
    selected_count: int
    status: str


@dataclass
class CallbackEvent:
    callback_id: str
    callback_type: str
    callback_payload: str
    user_id: Optional[str]
    created_at: Optional[str]


@dataclass
class SourceRegistryRecord:
    source_id: str
    source_type: str
    source_name: str
    source_url: Optional[str]
    enabled: bool


@dataclass
class SourceHealth:
    source_id: str
    checked_at: Optional[str]
    status: str
    details: Optional[str] = None


@dataclass
class AdminAction:
    action_id: str
    actor: str
    action_type: str
    payload: Optional[str]
    created_at: Optional[str]


@dataclass
class SystemEvent:
    event_id: str
    event_type: str
    severity: str
    message: str
    created_at: Optional[str]


@dataclass
class SendAttempt:
    attempt_id: str
    candidate_id: str
    sent_at: Optional[str]
    status: str
    error_message: Optional[str] = None


@dataclass
class LlmRun:
    run_id: str
    model: str
    prompt_type: str
    started_at: Optional[str]
    finished_at: Optional[str]
    status: str


@dataclass
class MigrationMapping:
    v2_table: str
    v2_id: str
    v3_table: str
    v3_id_or_external_id: str
    migrated_at: Optional[str]
    status: str


SCHEMA_DRAFT_TABLES = [
    "raw_news",
    "normalized_news",
    "scored_news",
    "publish_candidates",
    "published_messages",
    "full_articles",
    "digest_runs",
    "callback_events",
    "source_registry",
    "source_health",
    "admin_actions",
    "system_events",
    "send_attempts",
    "llm_runs",
    "migration_mapping",
    "rag_sources",
    "rag_documents",
    "document_versions",
    "legal_events",
    "shadow_runs",
    "shadow_rendered_posts",
]
