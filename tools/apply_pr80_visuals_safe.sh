#!/usr/bin/env bash
set -euo pipefail

cd /opt/newsbot_v2

TS="$(date +%F_%H%M%S)"
TMP="/tmp/newsbot_v3_pr80_safe_apply"
BACKUP="/opt/newsbot_v2/backups/before_pr80_safe_apply_${TS}.tar.gz"

SELECTED_BRANCH=""
AUDIO_RETRY_PRESERVED=false
VISUAL_ASSETS_PRESENT=false
SELLER_HELPER_CTA_PRESENT=false
FULL_ARTICLE_WORKER_UPDATED=false
FULL_ARTICLE_EDIT_IN_PLACE_PRESENT=false
PR80_DOES_NOT_INCLUDE_TOP_LEVEL_FULL_ARTICLE_WORKER=false

echo "PR80_SAFE_APPLY_BEGIN=$TS"
echo "--- reading passport ---"
test -f /opt/newsbot_v2/PROJECT_PASSPORT.md
grep -nEi "паспорт|PROJECT|audio|аудио|Seller Helper|full_article|Читать полностью|mascot|visual|cron" /opt/newsbot_v2/PROJECT_PASSPORT.md | tail -80 || true

echo "--- creating backup ---"
tar -czf "$BACKUP" newsbot_v3 PROJECT_PASSPORT.md full_article_callback_worker.py
echo "BACKUP=$BACKUP"

echo "--- fetching ecosystem ---"
git fetch ecosystem '+refs/heads/*:refs/remotes/ecosystem/*' '+refs/pull/*/head:refs/remotes/ecosystem/pr/*'

branch_has_visual() {
  local br="$1"
  git ls-tree -r --name-only "$br" 2>/dev/null | grep -qE 'test_visual_assets_and_cta.py|test_full_article_and_mascot.py|normalize_mascot_assets.py|mascot_assets.py'
}

branch_has_audio_retry() {
  local br="$1"
  git show "$br:newsbot_v3/tools/v3_audio_digest_send.py" 2>/dev/null | grep -q "audio_send_attempts"
}

echo "--- selecting branch ---"
CANDIDATES=(
  "ecosystem/pr/80"
  "ecosystem/codex/fix-full_article-ux-and-normalize-mascot-assets"
  "ecosystem/codex/restore-seller-helper-cta-and-add-mascot-selection"
  "ecosystem/main"
  "ecosystem/pr/79"
)

for br in "${CANDIDATES[@]}"; do
  if git rev-parse --verify "$br" >/dev/null 2>&1; then
    hv=no
    ha=no
    branch_has_visual "$br" && hv=yes || true
    branch_has_audio_retry "$br" && ha=yes || true
    echo "BR_CHECK=$br visual=$hv audio_retry=$ha"
    if [ "$hv" = "yes" ] && [ "$ha" = "yes" ]; then
      SELECTED_BRANCH="$br"
      break
    fi
  fi
done

if [ -z "$SELECTED_BRANCH" ]; then
  echo "PR80_SAFE_APPLY_STATUS=FAIL"
  echo "reason=no_branch_with_visual_and_audio_retry"
  exit 1
fi

echo "SELECTED_BRANCH=$SELECTED_BRANCH"

echo "--- archive selected branch ---"
rm -rf "$TMP"
mkdir -p "$TMP"

ARCHIVE_PATHS=(newsbot_v3)

if git cat-file -e "$SELECTED_BRANCH:PROJECT_PASSPORT.md" 2>/dev/null; then
  ARCHIVE_PATHS+=(PROJECT_PASSPORT.md)
fi

if git cat-file -e "$SELECTED_BRANCH:full_article_callback_worker.py" 2>/dev/null; then
  ARCHIVE_PATHS+=(full_article_callback_worker.py)
else
  PR80_DOES_NOT_INCLUDE_TOP_LEVEL_FULL_ARTICLE_WORKER=true
fi

echo "ARCHIVE_PATHS=${ARCHIVE_PATHS[*]}"
git archive "$SELECTED_BRANCH" "${ARCHIVE_PATHS[@]}" | tar -x -C "$TMP"

echo "--- temp files ---"
find "$TMP" -type f | grep -E 'test_visual_assets_and_cta.py|test_full_article_and_mascot.py|normalize_mascot_assets.py|mascot_assets.py|full_article_callback_worker.py|v3_audio_digest_send.py' | sort || true

echo "--- validate audio retry in temp ---"
if grep -R "audio_send_attempts" -n "$TMP/newsbot_v3/tools/v3_audio_digest_send.py" >/dev/null 2>&1 \
   && grep -R "attachment.not.ready" -n "$TMP/newsbot_v3/tools/v3_audio_digest_send.py" >/dev/null 2>&1 \
   && grep -R "time.sleep(8)" -n "$TMP/newsbot_v3/tools/v3_audio_digest_send.py" >/dev/null 2>&1; then
  AUDIO_RETRY_PRESERVED=true
else
  echo "PR80_SAFE_APPLY_STATUS=FAIL"
  echo "reason=audio_retry_missing_in_selected_branch"
  exit 1
fi

echo "--- validate visual / mascot / CTA signs in temp ---"
VISUAL_HITS="$(grep -R "visual_assets_enabled\|source_image_present\|mascot_asset_selected\|choose_visual_asset\|normalize_mascot_assets\|mascot_assets" -n "$TMP/newsbot_v3" 2>/dev/null | head -80 || true)"
CTA_HITS="$(grep -R "seller_helper_cta_after_news\|send_text_with_url_button\|🤝 Открыть Seller Helper\|Seller Helper" -n "$TMP/newsbot_v3" "$TMP/full_article_callback_worker.py" 2>/dev/null | head -80 || true)"

if [ -n "$VISUAL_HITS" ]; then
  VISUAL_ASSETS_PRESENT=true
fi

if [ -n "$CTA_HITS" ]; then
  SELLER_HELPER_CTA_PRESENT=true
fi

echo "$VISUAL_HITS"
echo "$CTA_HITS"

if [ "$VISUAL_ASSETS_PRESENT" != "true" ]; then
  echo "PR80_SAFE_APPLY_STATUS=FAIL"
  echo "reason=visual_assets_signs_missing"
  exit 1
fi

echo "--- temp tests ---"
TESTS=()
for f in \
  "$TMP/newsbot_v3/tests/test_visual_assets_and_cta.py" \
  "$TMP/newsbot_v3/tests/test_v3_controlled_send_canary_fail_closed.py" \
  "$TMP/newsbot_v3/tests/test_v3_audio_digest_send.py" \
  "$TMP/newsbot_v3/tests/test_max_client_real_send.py" \
  "$TMP/newsbot_v3/tests/test_full_article_and_mascot.py"
do
  [ -f "$f" ] && TESTS+=("$f")
done

if [ "${#TESTS[@]}" -eq 0 ]; then
  echo "PR80_SAFE_APPLY_STATUS=FAIL"
  echo "reason=no_tests_found"
  exit 1
fi

echo "TEMP_TESTS=${TESTS[*]}"
PYTHONPATH="$TMP/newsbot_v3:$TMP" /opt/newsbot_v2/venv/bin/python -m pytest -q "${TESTS[@]}"

echo "--- applying newsbot_v3 ---"
rm -rf /opt/newsbot_v2/newsbot_v3
cp -a "$TMP/newsbot_v3" /opt/newsbot_v2/newsbot_v3

if [ -f "$TMP/full_article_callback_worker.py" ]; then
  cp -a "$TMP/full_article_callback_worker.py" /opt/newsbot_v2/full_article_callback_worker.py
  FULL_ARTICLE_WORKER_UPDATED=true
else
  FULL_ARTICLE_WORKER_UPDATED=false
  echo "FULL_ARTICLE_WORKER_NOT_UPDATED=true"
fi

echo "--- post-apply checks ---"
grep -R "audio_send_attempts\|attachment.not.ready\|time.sleep(8)" -n /opt/newsbot_v2/newsbot_v3/tools/v3_audio_digest_send.py | head -80

grep -R "visual_assets_enabled\|source_image_present\|mascot_asset_selected\|choose_visual_asset\|normalize_mascot_assets\|mascot_assets" -n /opt/newsbot_v2/newsbot_v3 2>/dev/null | head -120 || true
grep -R "seller_helper_cta_after_news\|send_text_with_url_button\|🤝 Открыть Seller Helper\|Seller Helper" -n /opt/newsbot_v2/newsbot_v3 /opt/newsbot_v2/full_article_callback_worker.py 2>/dev/null | head -120 || true

echo "--- workdir tests ---"
WORK_TESTS=()
for f in \
  /opt/newsbot_v2/newsbot_v3/tests/test_visual_assets_and_cta.py \
  /opt/newsbot_v2/newsbot_v3/tests/test_v3_controlled_send_canary_fail_closed.py \
  /opt/newsbot_v2/newsbot_v3/tests/test_v3_audio_digest_send.py \
  /opt/newsbot_v2/newsbot_v3/tests/test_max_client_real_send.py \
  /opt/newsbot_v2/newsbot_v3/tests/test_full_article_and_mascot.py
do
  [ -f "$f" ] && WORK_TESTS+=("$f")
done

echo "WORK_TESTS=${WORK_TESTS[*]}"
PYTHONPATH=/opt/newsbot_v2/newsbot_v3:/opt/newsbot_v2 /opt/newsbot_v2/venv/bin/python -m pytest -q "${WORK_TESTS[@]}"

echo "--- full_article edit-in-place detection ---"
if grep -q "max_message_id" /opt/newsbot_v2/full_article_callback_worker.py \
   && grep -Eq "edit_original|requests\.put|api_put|PUT|/messages" /opt/newsbot_v2/full_article_callback_worker.py \
   && grep -Eiq "seller_helper|Seller Helper|SELLER_HELPER" /opt/newsbot_v2/full_article_callback_worker.py; then
  FULL_ARTICLE_EDIT_IN_PLACE_PRESENT=true
else
  FULL_ARTICLE_EDIT_IN_PLACE_PRESENT=false
fi

echo "--- update passport ---"
cat >> /opt/newsbot_v2/PROJECT_PASSPORT.md <<EOF

## ${TS} — PR80 safe apply status

Selected branch:
- ${SELECTED_BRANCH}

Applied:
- newsbot_v3 replaced from selected branch
- full_article_callback_worker.py updated: ${FULL_ARTICLE_WORKER_UPDATED}

Checks:
- audio retry preserved: ${AUDIO_RETRY_PRESERVED}
- visual/mascot assets present: ${VISUAL_ASSETS_PRESENT}
- Seller Helper CTA signs present: ${SELLER_HELPER_CTA_PRESENT}
- full_article edit-in-place detected in top-level worker: ${FULL_ARTICLE_EDIT_IN_PLACE_PRESENT}

Mandatory:
- Do not re-enable old stable publisher.
- Do not remove v3 audio attachment.not.ready retry behavior.
- Do not use URL button for "Читать полностью".
- Seller Helper CTA must remain under news where configured.

Pending if false:
- If full_article edit-in-place is false, create a separate PR for /opt/newsbot_v2/full_article_callback_worker.py so callback full_article:<id> edits the original MAX post and keeps Seller Helper CTA.
EOF

echo "PR80_SAFE_APPLY_STATUS=OK"
echo "SELECTED_BRANCH=$SELECTED_BRANCH"
echo "AUDIO_RETRY_PRESERVED=$AUDIO_RETRY_PRESERVED"
echo "VISUAL_ASSETS_PRESENT=$VISUAL_ASSETS_PRESENT"
echo "SELLER_HELPER_CTA_PRESENT=$SELLER_HELPER_CTA_PRESENT"
echo "FULL_ARTICLE_WORKER_UPDATED=$FULL_ARTICLE_WORKER_UPDATED"
echo "PR80_DOES_NOT_INCLUDE_TOP_LEVEL_FULL_ARTICLE_WORKER=$PR80_DOES_NOT_INCLUDE_TOP_LEVEL_FULL_ARTICLE_WORKER"
echo "FULL_ARTICLE_EDIT_IN_PLACE_PRESENT=$FULL_ARTICLE_EDIT_IN_PLACE_PRESENT"

if [ "$FULL_ARTICLE_EDIT_IN_PLACE_PRESENT" != "true" ]; then
  echo "NEXT_REQUIRED_PR=fix_top_level_full_article_callback_worker_edit_original"
fi
