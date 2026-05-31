# Feature parity checklist

| v2 feature | v2 file/service | v3 module | migration status | acceptance test |
|---|---|---|---|---|
| collector | collector_v2.py | app/collector/* | in progress (dry-run source migration) | v3_dry_run_pipeline.py |
| official GitHub JSON flow | official_channel_collector.py | app/collector/official_json_collector.py | dry-run strengthened | official_json dry-run |
| read-more internal fullarticle | publisher.py/full_article_callback_worker.py | app/publisher/post_builder.py + app/fullarticle/callback_worker.py | implemented skeleton | callback payload full_article:<id> |
| source inventory + coverage | parsers.py + telegram_json_sources_v2.py + env | tools/inventory_v2_sources.py + app/monitoring/source_coverage.py | implemented dry-run | inventory + healthcheck |
| legacy dangerous cleanup | cleanup_by_retention_policy | docs retention | redesign, do not port blindly | policy check |

## Dry-run source parity table

| v2 source type | v2 implementation | v3 adapter | status | dry-run acceptance |
|---|---|---|---|---|
| RSS | `newsbot_v2/parsers.py` | `app/collector/rss_collector.py` | connected | count from v2 inventory + per-source health |
| TG JSON | `newsbot_v2/telegram_json_sources_v2.py` | `app/collector/telegram_collector.py` | connected | `TG_JSON_URLS` count + mock fetch |
| Official GitHub JSON | env/url feed | `app/collector/official_json_collector.py` | primary | supports `OFFICIAL_JSON_URL(S)` + list/dict payload |
| Official WB | v2 official baseline | `app/monitoring/source_coverage.py` | OK | explicit coverage status |
| Official Ozon | v2 official baseline | `app/monitoring/source_coverage.py` | OK | explicit coverage status |
| Official Yandex | not fully mirrored | `app/monitoring/source_coverage.py` | WARN | explicit gap, not hidden |
| Direct TG official parsing | optional in v2 | official_json fallback mode | explicit fallback only | never default in dry-run |


## Read-more policy parity

| v2 behavior | v3 rule | status | acceptance |
|---|---|---|---|
| Some posts were too short for useful full-text callback | Add callback only when full text materially longer and above thresholds | implemented contract | long=button, short=no button, source link always present |
| Read-more could be interpreted as external link | `📖 Читать полностью` is internal callback only (`full_article:<id>`) | enforced contract | no external URL read-more button |

## Step 4 parity: scoring/LLM seller output
- llm_router supports dry-run modes: `disabled`, `primary_ok_mock`, `primary_fail_fallback_ok_mock`, `all_fail_template_fallback_mock`.
- Conservative fallback is mandatory when provider disabled/fails.
- Importance classification rules: 🔴 direct impact, 🟡 useful context, 🔵 background/low action.
- Source link always visible when `item.link` exists.
- Read-more is internal callback only and only when useful for long text.

## Step 5 publisher dry-run + MAX mock
- Dry-run chain: source/migrated -> scoring/seller output -> post builder -> MAX mock send -> mock message_id -> send_attempt/published_message plan.
- MAX mock only: no real sends, deterministic mock message_id, external URL button forbidden.
- SendAttempt/PublishedMessage are planned objects only; no DB mark until confirmed send.
- Seller Helper CTA is separate second message; CTA failure does not rollback main post.
- Read-more is internal callback only: full_article:<id>.

