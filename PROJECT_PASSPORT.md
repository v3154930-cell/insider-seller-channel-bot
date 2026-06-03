# PROJECT PASSPORT — Insider Seller / NEWSBOT / Seller Helper

## Current runtime state

Working branch: apply-pr93-canary-20260528-214310.

Current priority: keep NEWSBOT regular publishing alive and stable. Broad news flow is preferred over an over-filtered empty channel. Improve quality only with small targeted changes based on real posts.

## Key recent commits

- 251bf66 Reduce regular post truncation
- 9862a80 Use neutral regular mascot by default
- 59ff64a Use broad queue gateway and regular visual context
- cc4a843 Preserve official signal bridge routing
- 1f045f5 Commit official JSON channel posts
- 883d65a Merge Gosuslugi native ad false positive fix

## Main live contour

Regular publisher:
/opt/newsbot_v2/newsbot_v3/tools/v3_controlled_send_canary.py

Queue gateway:
/opt/newsbot_v2/queue_prepare_v3.py

Current queue policy: broad gateway. Do not tighten filters globally without explicit approval. Duplicates and native-ad garbage should be fixed with narrow rules only.

## Official marketplace sources

Official sources are collected through GitHub JSON, not direct Telegram scraping.

Flow:
official_marketplace_posts.json -> official_channel_collector.py -> official_channel_posts -> official_signal_monitor.py -> tariff_signals -> official_signal_bridge.py -> news

Important files:
- official_channel_collector.py
- official_signal_monitor.py
- official_signal_bridge.py
- run_official_signals_v2.sh

## Visual / mascot

Mascot selector:
newsbot_v3/app/visual/mascot_assets.py

Regular canary passes topic_tags, title, text and source into the selector. Neutral regular fallback is interesting_news, not base_friendly.

If mascot selection is wrong, fix mascot_assets.py first. Do not change queue or publisher for a visual-routing issue.

## Regular post text

Post text and truncation files:
- newsbot_v3/app/publisher/post_builder.py
- newsbot_v3/app/scoring/llm_router.py
- newsbot_v3/app/scoring/fallback_rules.py

Recent fix: regular post summary/fallback became longer, raw fallback expanded to about 1600 characters.

If DB title already contains ..., inspect raw_text. Old source titles may already be truncated.

## Runtime/cache files

Do not commit runtime/API cache files unless explicitly requested:
- rules_docs/api_cache/yandex_*
- rules_docs/api_cache/wb_commissions.json
- logs
- runtime DB files
- temporary backups

## Safe checks

Python compile:
python -m py_compile queue_prepare_v3.py newsbot_v3/tools/v3_controlled_send_canary.py newsbot_v3/app/visual/mascot_assets.py newsbot_v3/app/publisher/post_builder.py newsbot_v3/app/scoring/llm_router.py newsbot_v3/app/scoring/fallback_rules.py official_channel_collector.py official_signal_monitor.py official_signal_bridge.py

Dry-run regular publisher only, no live send unless explicitly allowed:
cd /opt/newsbot_v2 && set -a && . ./.env && set +a && PYTHONPATH=/opt/newsbot_v2/newsbot_v3:/opt/newsbot_v2 NEWSBOT_V3_PRODUCTION_SEND=true NEWSBOT_V3_SEND_MASCOT_ATTACHMENTS=false NEWSBOT_V3_MAX_CANDIDATE_ATTEMPTS_PER_RUN=10 /opt/newsbot_v2/venv/bin/python newsbot_v3/tools/v3_controlled_send_canary.py

Live health check:
cd /opt/newsbot_v2 && date && tail -n 180 logs/v3_publish.log && sqlite3 /opt/newsbot_v2/news_queue.db "SELECT id,source,seller_decision,seller_relevance_score,actionability_score,is_published,max_message_id,substr(title,1,260) FROM news WHERE seller_decision=publish AND COALESCE(is_published,0)=0 AND COALESCE(max_message_id,)= ORDER BY id DESC LIMIT 30;"

## Next development tasks

1. Normalize GitHub repository state for Codex.
2. Diagnose whether LLM actually works or mostly falls back to rules.
3. Improve audio digest as a separate product without touching regular publishing.
4. Clean duplicates and native ads with narrow rules only.

## Rules for future work

- Read this passport first.
- Do not create new runtime documentation files unless explicitly requested.
- Do not add new layers unless replacing old conflicting logic.
- Do not break the current working regular publisher.
- If problem is visual: mascot_assets.py.
- If problem is post text: post_builder.py or scoring.
- If problem is empty queue: queue_prepare_v3.py.
- If problem is official sources: official_* scripts.
