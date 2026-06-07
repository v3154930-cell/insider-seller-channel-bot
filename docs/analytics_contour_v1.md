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
