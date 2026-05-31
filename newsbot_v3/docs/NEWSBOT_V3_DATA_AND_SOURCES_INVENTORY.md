# Data and Sources Inventory

Step 3 after PR #42/#43: v3 DB/schema draft + migration dry-run (read-only) for `news_queue.db`.

## V3 schema table matrix

Core: `raw_news`, `normalized_news`, `scored_news`, `publish_candidates`, `published_messages`, `full_articles`, `digest_runs`, `callback_events`, `source_registry`, `source_health`, `admin_actions`, `system_events`, `send_attempts`, `llm_runs`, `migration_mapping`.
Future-ready: `rag_sources`, `rag_documents`, `document_versions`, `legal_events`.

## v2 -> v3 migration mapping (dry-run)

- `news` -> `raw_news`, `normalized_news`, `scored_news`, `publish_candidates`.
- `news` published flags/message metadata -> `published_messages` (preserve status, preserve `max_message_id` if present).
- `news` full text fields -> `full_articles`.
- digest-related traces (if detectable) -> `digest_runs`.
- Every migrated row gets record in `migration_mapping` for idempotency.

## Duplicate prevention strategy

Stable `external_id`/hash from: `source + link + title + published_at/content_hash`.
`migration_mapping` columns: `v2_table`, `v2_id`, `v3_table`, `v3_id_or_external_id`, `migrated_at`, `status`.
No repost of already published v2 items.

## Migration safety baseline

- production mutation: false;
- v2 DB access: read-only URI mode;
- v3 DB creation: disabled by default (plan only);
- real migration: only explicit operator command after backup.
