

---

## Runtime state — 2026-05-31

Рабочая ветка NEWSBOT: apply-pr93-canary-20260528-214310.

Ключевые коммиты текущего состояния: 251bf66 Reduce regular post truncation; 9862a80 Use neutral regular mascot by default; 59ff64a Use broad queue gateway and regular visual context; cc4a843 Preserve official signal bridge routing; 1f045f5 Commit official JSON channel posts; 883d65a Merge Gosuslugi native ad false positive fix.

Текущий режим: канал должен регулярно публиковать. Широкий поток новостей сейчас лучше, чем пустой канал из-за слишком строгих фильтров.

Главный regular publisher: /opt/newsbot_v2/newsbot_v3/tools/v3_controlled_send_canary.py.

Главный шлюз очереди: /opt/newsbot_v2/queue_prepare_v3.py.

Official marketplace sources работают через GitHub JSON: official_marketplace_posts.json -> official_channel_collector.py -> official_channel_posts -> official_signal_monitor.py -> tariff_signals -> official_signal_bridge.py -> news.

Visual selector: /opt/newsbot_v2/newsbot_v3/app/visual/mascot_assets.py. Regular canary передаёт topic_tags, title, text, source. Нейтральный regular fallback теперь interesting_news, а не base_friendly.

Текст regular-поста: newsbot_v3/app/publisher/post_builder.py, newsbot_v3/app/scoring/llm_router.py, newsbot_v3/app/scoring/fallback_rules.py. Summary/fallback стали длиннее, raw fallback расширен примерно до 1600 символов.

Runtime/cache Яндекса rules_docs/api_cache/yandex_*.json без отдельного решения не коммитить.

Правило следующих работ: сначала читать этот паспорт. После важной сессии обновлять этот же паспорт, не создавать новые runtime-документы. Канал должен жить; качество доводить точечно по фактическим постам; не плодить новые слои.
