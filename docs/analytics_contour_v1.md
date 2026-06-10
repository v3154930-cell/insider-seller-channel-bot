# Analytics contour v1

Analytics contour v1 is a safe MVP for future 7/30-day and quarterly Insider Seller / NEWSBOT analytics. It is manual-only: it does not call an LLM, publish posts, change cron, add UI/PDF, or alter Seller Helper.

## Source of truth

`/opt/newsbot_v2/data/unified_tariffs.db` is the source of truth for numeric tariff, commission, and fee calculations.

`/opt/newsbot_v2/data/rag_store.db` is for explanations, context, analytics, legal/docobrazec/offerdoctor materials, official documents, and news signals. RAG may explain a change, but must not replace tariff calculations from `unified_tariffs.db`.

TG/media are early-warning signals only. They are not authoritative for tariff calculations because they may be incomplete or interpretive. Any tariff signal must be validated against official sources and `unified_tariffs.db`.

## RAG layers

`news_signal`, `official_signal`, `legal_official`, `tariff_official`, `analytics_periodic`, `docobrazec_base`, `offer_doctor_base`, `internal_rule`.

## Added tables

- `analytics_source_registry` — planned source metadata and trust/layer registry.
- `analytics_reports` — generated draft analytics reports.
- `analytics_requests` — future user analytics requests.
- `analytics_user_limits` — future free/paid request limits.

## Commands

```bash
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/rag_healthcheck_v1.py
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/init_analytics_source_registry_v1.py
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/init_analytics_schema_v1.py
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/build_analytics_periodic_draft_v1.py --days 7 --marketplace all
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/build_analytics_periodic_draft_v1.py --days 30 --marketplace wildberries --topic tariff
```

## Do not touch live NEWSBOT

Do not modify or depend on changes to `run_v3_queue_prepare_once.sh`, `run_v3_publish_once.sh`, `newsbot_v3/tools/v3_controlled_send_canary.py`, `newsbot_v3/app/publisher/post_builder.py`, the V3 publisher, LLM editor, `full_article` button, Seller Helper CTA, cron, or `publisher_v2/formatters.py` for regular V3 posts.

## Periodic draft quality v2

`build_analytics_periodic_draft_v1.py` remains a deterministic, no-LLM draft builder, but the draft ranking is cleaned before human-facing report text is saved to `analytics_reports`.

Quality v2 behavior:

- Promotional, native-ad, leadgen, webinar/course, bot-sale, discount, quota, and similar service-sale rows are **not deleted from the database**. They are only excluded from top-news ranking and counted in `filtered_out_summary`.
- Internal routing and pipeline tags are hidden from user-facing report text. Examples include `seller_filter_live`, `queue_prepare_v3`, `official_signal_bridge`, `group_key=...`, `signal_ids=...`, `collector_routing`, `semantic_duplicate`, `weak_publish_to_digest`, and `seller_impact_to_publish`.
- Known internal topic tags are normalized into readable labels, for example `commission_tariff` becomes `tariffs/commissions`, `logistics_storage` becomes `logistics/storage`, and `returns_disputes` becomes `returns/disputes`.
- Draft fields use the fixed `analytics_reports` schema and separate official signals, marketplace breakdown, topic breakdown, TG/media context, items needing official validation, and filtered-out summary inside existing text fields.
- Top-news scoring stays deterministic: seller relevance and actionability remain the base, official sources are boosted, direct actionable-change language is boosted, promo/native rows are strongly penalized and filtered out of top ranking, unknown marketplace rows are slightly penalized, and older rows inside the selected period receive a small recency penalty.

Example commands:

```bash
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/build_analytics_periodic_draft_v1.py --days 7 --marketplace all
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/build_analytics_periodic_draft_v1.py --days 30 --marketplace wildberries --topic tariff
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/build_analytics_periodic_draft_v1.py --days 7 --marketplace all --limit-top 15 --include-filtered-debug
```

## Official legal/compliance/marketplace RAG sources

`newsbot_v3/tools/ingest_official_rag_sources_v1.py` is a dry-run-first foundation for loading official/public legal, compliance, tax, tariff, marketplace-offer, and seller-template documents into `/opt/newsbot_v2/data/rag_store.db`.

Safety rules:

- RAG remains explanatory and contextual. It can support analytics, Seller Helper explanations, Docobrazec, and future OfferDoctor checks, but it must not become the calculator for numeric tariff, commission, storage, logistics, or fee values.
- `/opt/newsbot_v2/data/unified_tariffs.db` remains the source of truth for numeric tariff calculations.
- Commercial legal databases such as Consultant, Garant, or similar services are excluded and must not be scraped or ingested.
- Only official/public sources and public marketplace documentation are allowed. The v1 allowlist is deterministic and limited to official Russian legal/regulatory/tax/compliance domains plus public seller documentation domains already used by the project.
- The seed registry lives in `newsbot_v3/config/official_rag_sources_v1.json` and extends the existing `analytics_source_registry`; it is not a second source registry. `init_analytics_source_registry_v1.py` mirrors those planned sources into `analytics_source_registry` without changing publisher runtime behavior.
- If an existing production `analytics_source_registry` still has the original v1 CHECK constraints, new conceptual categories are recorded through legacy-compatible registry layers instead of running a destructive migration: `marketplace_offer` → `official_signal`, `compliance_official`/`tax_official` → `legal_official`, and `seller_templates` → `docobrazec_base`, with the requested layer preserved in notes. Fresh databases use the extended layer list directly.
- The ingestion tool refuses non-allowlisted URLs, accepts only `text/html` and `text/plain`, uses a timeout and max document size limit, extracts title and clean text, computes a SHA-256 content hash, and skips duplicates by `content_hash` and/or `source_url` when those columns exist.

Dry-run first deployment process:

```bash
cd /opt/newsbot_v2
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/rag_healthcheck_v1.py
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/init_analytics_source_registry_v1.py
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/ingest_official_rag_sources_v1.py --dry-run --limit 5
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/ingest_official_rag_sources_v1.py --dry-run --layer legal_official --limit 3
```

After reviewing the dry-run report (`source_key`, URL, layer, status, title, clean text length, content hash, and inserted/skipped reason), run a narrow non-dry-run command for a specific reviewed source only:

```bash
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/ingest_official_rag_sources_v1.py --source-key pravo_legal_publication_portal --limit 1
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/rag_healthcheck_v1.py
```

This process does not modify cron, publisher runtime logic, MAX sending logic, or live publishing behavior.
