# Redundancy and Failover

Collector retries per-source; official JSON primary, TG fallback explicit only; LLM primary/fallback/template; MAX retry/backoff; digest retries; audio attachment.not.ready retry; fullarticle target fallback; admin read-only fallback.

## Step 5 publisher dry-run + MAX mock
- Dry-run chain: source/migrated -> scoring/seller output -> post builder -> MAX mock send -> mock message_id -> send_attempt/published_message plan.
- MAX mock only: no real sends, deterministic mock message_id, external URL button forbidden.
- SendAttempt/PublishedMessage are planned objects only; no DB mark until confirmed send.
- Seller Helper CTA is separate second message; CTA failure does not rollback main post.
- Read-more is internal callback only: full_article:<id>.



## Step 6 limited live test-channel
- Default remains dry-run/mock (`NEWSBOT_V3_REAL_SEND=false`, `NEWSBOT_V3_MOCK_MAX=true`).
- Limited live requires strict fail-closed guards and only `NEWSBOT_V3_TEST_CHANNEL_ID` target.
- No production cutover in this PR; v2 remains production.
- Rollback: set `NEWSBOT_V3_REAL_SEND=false`.
- Inspect runtime writes only in `V3_DB` (`published_messages`, `send_attempts`, `system_events`).
- Fullarticle callback payload in long posts must be `full_article:<id>`; live callback worker is next PR.


## Step 6.5 shadow/rehearsal interim mode
- MAX real test channel currently blocked by advance moderation/creation requirements.
- Production channel must not be used for testing.
- Shadow/rehearsal mode is the safe interim step before any live test or cutover.
- Shadow mode reads v2 DB in read-only mode and never mutates v2 records/state.
- Shadow mode never sends to MAX (`max_send=false`) and writes only to v3 runtime DB (`shadow_runs`, `shadow_rendered_posts`, `system_events`, `send_attempts` with `status=shadow_no_send`).
- Inspect results with: `sqlite3 $V3_DB "select id,created_at,source,v2_news_id,status from shadow_runs order by id desc limit 20;"` and `sqlite3 $V3_DB "select shadow_run_id,substr(post_text,1,120),read_more_needed,read_more_payload from shadow_rendered_posts order by id desc limit 20;"`.
- Real send remains blocked until approved test target is available.
- Shadow sample scenario is smoke-test only; real v2 rehearsal must use read-only adapter (`app/collector/v2_news_adapter.py`) against `/opt/newsbot_v2/news_queue.db?mode=ro`.
- Verify latest rendered shadow output in `shadow_rendered_posts` before any future MAX live-test/cutover decision.

## Legal/tax/regulatory contour foundation
- Legal/tax/regulatory sources are first-class alongside marketplace channels, but currently registry-only.
- No live crawling in this step; network-disabled dry-run validation only.
- FNS API credentials are never stored in repo; adapter rollout is deferred to a separate PR.
- Legal/tax content must include source/date/link/status and neutral wording for high-risk topics.
- LLM output must not invent legal interpretation; unresolved cases stay `impact_uncertain`.
