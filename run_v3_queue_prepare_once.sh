#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
PY=python3
[[ -x /opt/newsbot_v2/venv/bin/python ]] && PY=/opt/newsbot_v2/venv/bin/python

echo "queue_prepare_started=1"
collector_ran=0; decision_ran=0; safety_promote_ran=0; errors="none"

emit_from_json() {
  local prefix="$1"; local json_file="$2"
  echo "${prefix}_raw_pending_publish_before=$($PY -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["raw_pending_publish_count_before"])' "$json_file")"
  echo "${prefix}_canary_checked_pending_ids=$($PY -c 'import json,sys;d=json.load(open(sys.argv[1]));print(",".join(map(str,d.get("canary_checked_pending_ids",[]))))' "$json_file")"
  echo "${prefix}_v3_eligible_pending_publish_before=$($PY -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["v3_eligible_pending_publish_count_before"])' "$json_file")"
  echo "${prefix}_demoted_noneligible_publish_count=$($PY -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["demoted_noneligible_publish_count"])' "$json_file")"
  echo "${prefix}_demoted_noneligible_publish_ids=$($PY -c 'import json,sys;d=json.load(open(sys.argv[1]));print(",".join(map(str,d["demoted_ids"])))' "$json_file")"
  echo "${prefix}_demoted_noneligible_publish_reasons=$($PY -c 'import json,sys;d=json.load(open(sys.argv[1]));print(json.dumps(d["demotion_reasons"],ensure_ascii=False))' "$json_file")"
  echo "${prefix}_raw_pending_publish_after=$($PY -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["raw_pending_publish_count_after"])' "$json_file")"
  echo "${prefix}_v3_eligible_pending_publish_after=$($PY -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["v3_eligible_pending_publish_count_after"])' "$json_file")"
}

first_json=/tmp/queue_prepare_first.json
if $PY queue_prepare_v3.py >"$first_json" 2>/tmp/queue_prepare_first.err; then
  emit_from_json first "$first_json"
else
  errors="1"
  echo "first_preflight_error=$(tr '\n' ' ' </tmp/queue_prepare_first.err | sed 's/[[:space:]]\+/ /g')"
fi

$PY collector_v2.py >/tmp/queue_prepare_collector.log 2>&1 || errors="${errors};collector_failed"
collector_ran=1
$PY promote_publish_candidates.py >/tmp/queue_prepare_decision.log 2>&1 || errors="${errors};decision_failed"
decision_ran=1
$PY safety_promote_ignored_to_publish_v1.py >/tmp/queue_prepare_safety.log 2>&1 || errors="${errors};safety_failed"
safety_promote_ran=1

final_v3_after=0
final_json=/tmp/queue_prepare_final.json
if $PY queue_prepare_v3.py >"$final_json" 2>/tmp/queue_prepare_final.err; then
  emit_from_json final "$final_json"
  # required final diagnostics without prefix
  echo "raw_pending_publish_before=$($PY -c 'import json;d=json.load(open("/tmp/queue_prepare_final.json"));print(d["raw_pending_publish_count_before"])')"
  echo "canary_checked_pending_ids=$($PY -c 'import json;d=json.load(open("/tmp/queue_prepare_final.json"));print(",".join(map(str,d.get("canary_checked_pending_ids",[]))))')"
  echo "v3_eligible_pending_publish_before=$($PY -c 'import json;d=json.load(open("/tmp/queue_prepare_final.json"));print(d["v3_eligible_pending_publish_count_before"])')"
  echo "demoted_noneligible_publish_count=$($PY -c 'import json;d=json.load(open("/tmp/queue_prepare_final.json"));print(d["demoted_noneligible_publish_count"])')"
  echo "demoted_noneligible_publish_ids=$($PY -c 'import json;d=json.load(open("/tmp/queue_prepare_final.json"));print(",".join(map(str,d["demoted_ids"])))')"
  echo "demoted_noneligible_publish_reasons=$($PY -c 'import json;d=json.load(open("/tmp/queue_prepare_final.json"));print(json.dumps(d["demotion_reasons"],ensure_ascii=False))')"
  echo "raw_pending_publish_after=$($PY -c 'import json;d=json.load(open("/tmp/queue_prepare_final.json"));print(d["raw_pending_publish_count_after"])')"
  final_v3_after="$($PY -c 'import json;d=json.load(open("/tmp/queue_prepare_final.json"));print(d["v3_eligible_pending_publish_count_after"])')"
  echo "v3_eligible_pending_publish_after=$final_v3_after"
else
  errors="${errors};final_preflight_failed"
  echo "final_preflight_error=$(tr '\n' ' ' </tmp/queue_prepare_final.err | sed 's/[[:space:]]\+/ /g')"
fi

if [[ "$final_v3_after" -gt 0 ]]; then
  echo "skip=already_has_pending_publish"
fi

publish_after="$($PY - <<'PY'
import os,sqlite3
p=os.getenv('NEWSBOT_DB_PATH','/opt/newsbot_v2/news_queue.db')
con=sqlite3.connect(p)
print(con.execute("SELECT COUNT(*) FROM news WHERE COALESCE(is_published,0)=0 AND seller_decision='publish'").fetchone()[0])
PY
)"
echo "collector_ran=$collector_ran"
echo "decision_ran=$decision_ran"
echo "safety_promote_ran=$safety_promote_ran"
echo "publish_candidates_after=$publish_after"
echo "errors=$errors"
