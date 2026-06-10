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

## Legal and court-practice RAG source discovery

A first legal/court-practice seed list lives in `newsbot_v3/config/legal_rag_sources_v1.json`. It is a **manual-review seed**, not an ingestion manifest: every row is marked `dry_run_first/manual_review_required`, and no live ingestion, DB schema migration, publisher change, cron change, MAX send, NEWSBOT publication behavior, or tariff calculation change is implied.

Scope of the seed list:

- Core official legal sources for marketplace sellers, Docobrazec, and OfferDoctor: consumer protection, retail sale rules, platform economy, Civil Code offer/acceptance/agency/commission/service/liability blocks, online cash registers, personal data, advertising, electronic signature, technical regulation, marking/Chestny Znak legal basis, and FNS tax explanations.
- Supreme Court materials: Plenum guidance, consumer-protection review materials, and selected definitions relevant to distance selling, product information, returns, and consumer claims.
- Public court-practice discovery entries for seller/platform disputes: marketplace penalties, blocked cards/accounts, withheld payouts, offer terms, marking/KIZ, intermediary/platform liability, product cards, counterfeit/IP disputes, and seller/product information.

Validation and trust policy:

- Do **not** ingest real documents from this seed until a manual reviewer confirms URL freshness, document status, and whether newer amendments or superseding guidance exist.
- Do **not** use Consultant, Garant, or other commercial legal database URLs as RAG sources. If a useful case is first discovered through a commercial snippet, replace it with an official/public concrete court-act URL before ingestion.
- Prefer official/public concrete document URLs over homepages. A homepage-only source should be rejected unless there is no public document alternative and the row explicitly remains a discovery lead.
- Ordinary arbitral/court decisions are marked lower-trust than Supreme Court materials and should be used only as illustrative practice, not as authoritative general rules.
- `unified_tariffs.db` remains the numeric source of truth for tariff, commission, and fee calculations; legal RAG may only explain context, obligations, and dispute practice.

Local validation command:

```bash
python -m pytest newsbot_v3/tests/test_legal_rag_sources_v1.py
```
