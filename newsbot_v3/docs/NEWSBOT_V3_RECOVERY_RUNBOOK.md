# Recovery Runbook

## Precondition
- Any real migration action must start from fresh DB backup (`news_queue.db` and v3 runtime DB if exists).

## If migration/cutover validation fails (future real step)
1. stop migration worker/process;
2. keep v2 publisher/runtime unchanged;
3. restore DB from backup snapshot;
4. verify published history consistency and `max_message_id` continuity;
5. rerun dry-runs before any retry.

## Step 3 scope
Only dry-run tools are introduced. No production writes, no cutover.


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


## Media fallback policy
- Image layer is optional (`image_required=false`) and cannot block text publication.
- Resolver order: valid external URL -> local neutral placeholder -> no image.
- Placeholder pack uses non-branded static SVG assets only (no trademarked logos).
- On image issues, continue with text-only and record fallback reason in diagnostics.

## Step 7 legal/tax/regulatory contour foundation
- Registry/config/classifier check is non-mutating (`production_mutation=false`).
- If registry validation fails, keep legal/tax sources disabled by default and continue core dry-run pipeline.
- Never commit FNS credentials; only placeholder env keys are allowed in config.
- FNS live API integration is postponed to a dedicated PR after user-provided API sample/document.

## Quality gate recovery notes
- If observer selects weak non-seller background item, do not force publish fallback.
- Verify `selection_quality_gate_status` and reason; expected skip for low-action background/legal non-seller.
- Recovery policy: better no post than irrelevant post for seller channel.

## Controlled production canary rollback
- Scope is one controlled canary post only; this is not cutover.
- Keep v2 as production publisher at all times in this step.
- If any anomaly: disable `NEWSBOT_V3_PRODUCTION_SEND` (and/or `NEWSBOT_V3_REAL_SEND=false`) to hard-stop v3 production send.
- v2 DB is never mutated by canary tool; no v2 published marks should appear.
- Verify duplicate-prevention markers in v3 runtime DB before any retry (`do_not_repost_published`).
- Read-more must remain internal callback (`full_article:<id>`); no external URL button allowed.

## PR81 dry-run commands (mascot visuals behind feature flag)
- Regular post dry-run (visuals disabled/default):
  - `python newsbot_v3/tools/v3_publisher_dry_run.py --scenario default`
- Regular post dry-run (visuals enabled):
  - `NEWSBOT_V3_ENABLE_MASCOT_IMAGES=true python newsbot_v3/tools/v3_publisher_dry_run.py --scenario default`
- Morning digest dry-run with visuals:
  - `NEWSBOT_V3_ENABLE_MASCOT_IMAGES=true python newsbot_v3/tools/v3_digest_send.py --kind morning`
- Final digest dry-run with visuals:
  - `NEWSBOT_V3_ENABLE_MASCOT_IMAGES=true python newsbot_v3/tools/v3_digest_send.py --kind final`
- Audio digest dry-run with visuals:
  - `NEWSBOT_V3_ENABLE_MASCOT_IMAGES=true python newsbot_v3/tools/v3_audio_digest_send.py`
- One live test instruction (do not run from tests): enable explicit production guards and run one controlled send only after operator approval.
