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


## Official RAG ingestion safety

Official RAG ingestion must be staged source-by-source before any batch run. Use `--source-key` for the first pass so only the reviewed registry entry is fetched and evaluated.

Safe single-source workflow:

```bash
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/ingest_official_rag_sources_v1.py --db /opt/newsbot_v2/data/rag_store.db --dry-run --source-key nalog_tax_official --layer legal_official
# Review dry-run output and confirm the selected source, URL, layer, and quality-gate result before writing rows.
/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/ingest_official_rag_sources_v1.py --db /opt/newsbot_v2/data/rag_store.db --source-key nalog_tax_official --layer legal_official
```

Do not run real batch ingestion until the dry-run for the exact `source_key` has been reviewed. Batch ingestion can insert official sources that still need manual review; the safe default is to ingest one source only, inspect the resulting RAG rows, and then proceed to the next source.

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
