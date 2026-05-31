# NEWSBOT V3 Migration Plan

## Completed
- PR #42: v3 foundation.
- PR #43: source migration dry-run and v2 source coverage.

## Step 3 (this PR)
- v3 schema SQL builder and validation.
- `v3_db_schema_dry_run.py` (no file creation, no writes).
- `v3_migration_dry_run.py` read-only planning from `/opt/newsbot_v2/news_queue.db`.

## Rules
- Dry-run first.
- Backup before real migration.
- Real migration requires explicit operator command.
- No cutover in this step.

## Rollback strategy
- If future real migration validation fails: stop v3 migration job, restore backup snapshot, continue v2 runtime unchanged.

## Duplicate prevention
- stable external_id/hash: `source + link + title + published_at/content_hash`.
- `migration_mapping` controls idempotency and replay safety.
- preserve published history and never repost old published news.

## Step 4 (this PR)
- v3 seller output/scoring/LLM dry-run.
- Conservative fallback for seller summary/conclusion and importance classification.
- Source link visibility policy and long-vs-short internal read-more callback decision.
- No cutover, no production writes, v2 runtime unchanged.

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
- Add optional media plan resolution for publisher dry-run/shadow only.
- External image preferred when valid; fallback to local neutral placeholder; final fallback text-only.
- Image send failure is non-blocking and does not rollback publication of text.
- No production cutover and no real MAX image send in this step.

## Step 7 legal/tax/regulatory contour foundation
- Add first-class legal/tax/marking/regulatory source registry and dry-run checks.
- No credentials in repo; FNS API adapter is a separate PR based on user-provided API sample/document.
- No live crawling/cutover in this step; defaults remain safe/dry-run.
- Classifier stubs provide conservative seller-impact mapping and neutral language requirements.

## Step 6.6 selection quality gate
- Add quality gate for real-v2 shadow/publisher: skip low-action background and non-seller legal fallback.
- For weak-only pools return no candidate with `selection_reason=skipped_low_action_background`.
- Keep defaults safe: no MAX real send, no v2 mutation, production_mutation=false.

## Step 6.7 controlled production send canary
- Add guarded tool `tools/v3_controlled_send_canary.py` for exactly one production canary text post.
- No full cutover; v2 remains production publisher.
- Default remains blocked/dry-run (`production_mutation=false`).
- Real send allowed only by explicit env + explicit CLI `--execute`.
- v2 DB is read-only source; no v2 row publish marking.
- v3 runtime records only after confirmed send: send_attempt + published_message + system_event(canary_send).
- Duplicate prevention uses v2_news_id and source+link+title hash to do_not_repost_published.
- Read-more uses only internal callback payload; external URL button forbidden.
- Rollback is immediate by disabling `NEWSBOT_V3_PRODUCTION_SEND`.

## PR69 Digest/Audio Cutover Runbook

Replacement cron examples (keep v2 jobs in place until verified):

- `0 6 * * * cd /opt/newsbot_v2 && /usr/bin/python3 /opt/newsbot_v3/tools/v3_digest_send.py --kind morning --execute`
- `0 23 * * * cd /opt/newsbot_v2 && /usr/bin/python3 /opt/newsbot_v3/tools/v3_digest_send.py --kind final --execute`
- `45 22 * * * cd /opt/newsbot_v2 && /usr/bin/python3 /opt/newsbot_v3/tools/v3_audio_digest_send.py --execute`

Cutover sequence:
1. Test v3 audio dry-run: `cd /opt/newsbot_v2 && /usr/bin/python3 /opt/newsbot_v3/tools/v3_audio_digest_send.py`
2. Test one v3 audio live send (with all production guards enabled): `cd /opt/newsbot_v2 && /usr/bin/python3 /opt/newsbot_v3/tools/v3_audio_digest_send.py --execute`
3. Then disable v2 `run_audio_digest.sh` cron entry.
4. Add v3 audio cron replacement: `45 22 * * * cd /opt/newsbot_v2 && /usr/bin/python3 /opt/newsbot_v3/tools/v3_audio_digest_send.py --execute`
5. Keep v2 scripts on disk for rollback.
