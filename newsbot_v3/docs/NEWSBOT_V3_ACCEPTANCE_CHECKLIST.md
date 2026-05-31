# Acceptance

## Step 3 acceptance (DB/schema + migration dry-run)

- no production DB writes
- no v2 file changes
- no MAX sends
- schema tables are listed in dry-run output
- migration dry-run opens v2 DB read-only
- published history preservation explicit
- duplicate prevention strategy explicit
- backup-before-real-migration rule documented
- rollback strategy documented
- WARN allowed only for no real migration/cutover and known source gaps

## Step 4 acceptance (seller output dry-run)
- seller output dry-run tool returns `V3_SELLER_OUTPUT_DRY_RUN_STATUS=OK|WARN|FAIL`.
- no production mutation, no MAX sends, no real LLM by default.
- long news -> callback `full_article:<id>`.
- short news -> no read-more button.
- source URL visible whenever `item.link` exists.
- external URL read-more button forbidden.

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

## Seller editorial framework policy
- 🔴 only when direct seller action exists (deadline/process/compliance risk).
- No fake universal advice (e.g., margin recalculation) unless commission/tariff/cost actually changed.
- legal/tax/regulatory and marking/Честный знак are first-class seller topics.
- corporate PR/ownership news is low-action by default unless concrete seller impact exists.
- Observer checks real-v2 shadow rendered posts for topic, actionability, no fake action, source link, and importance.


## Step 5.5 media/image placeholder pipeline
- Images are optional and must never block text publication.
- Prefer valid external image URL when present.
- If external image is missing, use neutral local SVG placeholder by topic/marketplace.
- If placeholder missing, fallback to text-only post without failure.
- No trademarked/logo-specific placeholders; only neutral owned static graphics.

## Step 7 legal/tax/regulatory contour foundation
- legal/tax/regulatory source registry exists in `config/legal_tax_sources.json`.
- FNS source is registered with placeholder env keys only (`FNS_API_BASE_URL`, `FNS_API_TOKEN`) and no credentials committed.
- no live crawling/network collection in this step; dry-run/registry-only validation.
- legal/tax classifier and seller impact mapping are deterministic stubs only.
- legal/tax posts require source/date/link/status in downstream rendering policy.
- LLM must not invent legal interpretation; high-risk topics use neutral wording.

## Selection quality gate (shadow/publisher)
- no direct action + low relevance/actionability must not be published as fallback after daily minimum.
- legal/regulatory is first-class only with seller/platform/tax/marking/document/fines-blocks-checks/platform-rules impact.
- observer may log weak items, but production selection must skip them.
- better no post than irrelevant post.

## Step 6.7 controlled production send canary
- Controlled one-post canary only (`v3_controlled_send_canary.py`), no automatic cutover.
- Default mode is dry-run and blocked for real production send.
- Execute requires explicit env guards + `--execute`; fail-closed if any guard missing.
- v2 remains production; v2 DB read-only only; no v2 mutation.
- Duplicate prevention: do_not_repost_published by v2_news_id and source+link+title hash in v3 runtime DB.
- Read-more button may be internal callback only (`full_article:<id>`); external URL button is forbidden.
- Rollback: disable `NEWSBOT_V3_PRODUCTION_SEND` and keep v2 production.
