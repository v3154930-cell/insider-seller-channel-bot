#!/usr/bin/env bash
set -u

cd /opt/newsbot_v2 || exit 1

TS="$(date +%Y%m%d_%H%M%S)"
LOG="/opt/newsbot_v2/reports/full_system_audit_v3_safe_${TS}.log"
PY="/opt/newsbot_v2/venv/bin/python"

{
echo "============================================================"
echo "FULL NEWSBOT SYSTEM AUDIT SAFE"
echo "at=$(date -Is)"
echo "host=$(hostname)"
echo "pwd=$(pwd)"
echo "log=$LOG"
echo "============================================================"

echo
echo "### 0. PASSPORT / PROJECT RULES"
echo "---- passport files ----"
ls -lah PROJECT_PASSPORT.md newsbot_v3/PROJECT_PASSPORT_V3.md 2>/dev/null || true
echo "---- passport important lines ----"
grep -RInE 'backup|py_compile|test|restart|journalctl|venv|publisher|watchdog|cron|v3|MAX|паспорт|read|update' PROJECT_PASSPORT.md newsbot_v3/PROJECT_PASSPORT_V3.md 2>/dev/null | sed -n '1,180p' || true

echo
echo "### 1. GIT STATE"
git branch --show-current || true
git log --oneline -8 || true
git status --short || true

echo
echo "### 2. BACKUP SNAPSHOT"
mkdir -p backups
cp -a news_queue.db "backups/news_queue_before_full_audit_${TS}.db" 2>/dev/null && echo "backup_db=backups/news_queue_before_full_audit_${TS}.db" || echo "backup_db=FAILED_OR_NO_DB"
cp -a .env "backups/env_before_full_audit_${TS}.bak" 2>/dev/null && echo "backup_env=backups/env_before_full_audit_${TS}.bak" || echo "backup_env=FAILED_OR_NO_ENV"

echo
echo "### 3. ENV SANITY WITHOUT SECRETS"
echo "---- .env relevant keys ----"
grep -nE '^(CHANNEL_ID|MAX_BOT_TOKEN|NEWSBOT_MAX_CHANNEL_ID|NEWSBOT_V3_)=' .env 2>/dev/null | sed -E 's/(TOKEN=).*/\1***hidden***/' || true
echo "---- suspicious root files ----"
ls -la 0 grep 2>/dev/null || true

echo
echo "### 4. CRON / SYSTEMD / AUTOSTART"
echo "---- user crontab ----"
crontab -l 2>/dev/null || true
echo "---- /etc cron grep ----"
grep -RInE 'newsbot|publisher|v3|digest|collector|watchdog|safety_promote|run_v3|stable_publisher' /etc/cron* /var/spool/cron 2>/dev/null | sed -n '1,260p' || true
echo "---- systemd timers ----"
systemctl list-timers --all 2>/dev/null | grep -Ei 'newsbot|publisher|v3|digest|collector|watchdog' || true
echo "---- systemd services ----"
systemctl list-units --type=service --all 2>/dev/null | grep -Ei 'newsbot|publisher|v3|digest|collector|watchdog|helper' || true

echo
echo "### 5. RUN SCRIPTS INVENTORY"
ls -lah run_publisher_safe_v1.sh run_stable_publisher_v3.sh run_v3_* stable_publisher_v3.py queue_prepare_v3.py safety_promote_ignored_to_publish_v1.py newsbot_healthcheck_v1.py 2>/dev/null || true
echo "---- run scripts content summary ----"
for f in run_publisher_safe_v1.sh run_stable_publisher_v3.sh run_v3_publish_once.sh run_v3_queue_prepare_once.sh run_v3_morning_digest.sh run_v3_final_digest.sh run_v3_audio_digest.sh; do
  if [ -f "$f" ]; then
    echo "----- $f -----"
    sed -n '1,220p' "$f"
  fi
done

echo
echo "### 6. PYTHON VERSION / IMPORT PATH"
"$PY" -V || true
"$PY" - <<'PY' || true
import sys, sqlite3
print("python=", sys.executable)
print("sqlite=", sqlite3.sqlite_version)
PY

echo
echo "### 7. PYCHECK CORE FILES"
"$PY" -m py_compile \
  safety_promote_ignored_to_publish_v1.py \
  queue_prepare_v3.py \
  stable_publisher_v3.py \
  newsbot_healthcheck_v1.py \
  newsbot_v3/app/max_client.py \
  newsbot_v3/app/publisher/post_builder.py \
  newsbot_v3/tools/v3_controlled_send_canary.py \
  newsbot_v3/tools/post_builder_dry_run_checks.py \
  newsbot_v3/tools/v3_healthcheck.py \
  newsbot_v3/tools/v3_dry_run_pipeline.py \
  newsbot_v3/tools/v3_publisher_dry_run.py \
  newsbot_v3/tools/v3_selection_quality_check.py \
  2>&1 || true

echo
echo "### 8. TESTS / REGRESSION"
if "$PY" -m pytest --version >/dev/null 2>&1; then
  "$PY" -m pytest -q newsbot_v3/tests 2>&1 || true
else
  echo "pytest_missing=true"
  "$PY" -m py_compile newsbot_v3/tests/*.py 2>&1 || true
fi

echo
echo "### 9. DATABASE QUEUE STATE"
"$PY" - <<'PY' || true
import sqlite3
from pathlib import Path
db = Path("/opt/newsbot_v2/news_queue.db")
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
print("db=", db)
print("tables=", [r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")])
print("\n-- today decision/published --")
for r in con.execute("""
    SELECT seller_decision, is_published, COUNT(*) c
    FROM news
    WHERE date(created_at)=date('now','localtime')
    GROUP BY seller_decision,is_published
    ORDER BY seller_decision,is_published
"""):
    print(dict(r))
print("\n-- pending publish --")
for r in con.execute("""
    SELECT id, score, source, seller_decision, seller_relevance_score, actionability_score, is_published, max_message_id, title
    FROM news
    WHERE seller_decision='publish'
      AND COALESCE(is_published,0)=0
      AND COALESCE(max_message_id,'')=''
    ORDER BY score DESC, created_at DESC
    LIMIT 20
"""):
    d=dict(r); d["title"]=(d["title"] or "")[:180]; print(d)
print("\n-- top unpublished digest --")
for r in con.execute("""
    SELECT id, score, source, seller_decision, is_published, title
    FROM news
    WHERE seller_decision IN ('digest','ignore')
      AND COALESCE(is_published,0)=0
      AND COALESCE(max_message_id,'')=''
    ORDER BY score DESC, created_at DESC
    LIMIT 30
"""):
    d=dict(r); d["title"]=(d["title"] or "")[:180]; print(d)
con.close()
PY

echo
echo "### 10. SAFETY PROMOTE DRY RUN ONLY"
NEWSBOT_SAFETY_PROMOTE_DRY_RUN=1 "$PY" safety_promote_ignored_to_publish_v1.py 2>&1 || true

echo
echo "### 11. POST BUILDER DRY RUN CHECKS"
PYTHONPATH=/opt/newsbot_v2/newsbot_v3 "$PY" newsbot_v3/tools/post_builder_dry_run_checks.py 2>&1 || true

echo
echo "### 12. V3 ENV DERIVED GUARD CHECK"
set -a
[ -f .env ] && . ./.env
set +a
NEWSBOT_V3_PRODUCTION_SEND=true \
NEWSBOT_V3_CUTOVER_CONFIRM=I_UNDERSTAND_V3_SENDS_TO_PRODUCTION \
NEWSBOT_V3_PRODUCTION_CHANNEL_ID="${NEWSBOT_V3_PRODUCTION_CHANNEL_ID:-${CHANNEL_ID:-}}" \
NEWSBOT_V3_TEST_CHANNEL_ID="${NEWSBOT_V3_TEST_CHANNEL_ID:-${CHANNEL_ID:-}}" \
NEWSBOT_MAX_CHANNEL_ID="${NEWSBOT_MAX_CHANNEL_ID:-${CHANNEL_ID:-}}" \
NEWSBOT_V3_ALLOW_PRODUCTION_CHANNEL="${NEWSBOT_V3_ALLOW_PRODUCTION_CHANNEL:-true}" \
NEWSBOT_V3_MAX_TOKEN="${NEWSBOT_V3_MAX_TOKEN:-${MAX_BOT_TOKEN:-}}" \
NEWSBOT_V3_MOCK_MAX="${NEWSBOT_V3_MOCK_MAX:-false}" \
NEWSBOT_V3_REAL_SEND="${NEWSBOT_V3_REAL_SEND:-true}" \
NEWSBOT_V3_MARK_V2_PUBLISHED="${NEWSBOT_V3_MARK_V2_PUBLISHED:-true}" \
"$PY" - <<'PY' || true
import os, sys
sys.path.insert(0, "/opt/newsbot_v2/newsbot_v3")
from app.max_client import MaxClient
print("env_present=", {
    "CHANNEL_ID": bool(os.getenv("CHANNEL_ID")),
    "MAX_BOT_TOKEN": bool(os.getenv("MAX_BOT_TOKEN")),
    "NEWSBOT_V3_PRODUCTION_CHANNEL_ID": bool(os.getenv("NEWSBOT_V3_PRODUCTION_CHANNEL_ID")),
    "NEWSBOT_V3_TEST_CHANNEL_ID": bool(os.getenv("NEWSBOT_V3_TEST_CHANNEL_ID")),
    "NEWSBOT_MAX_CHANNEL_ID": bool(os.getenv("NEWSBOT_MAX_CHANNEL_ID")),
    "NEWSBOT_V3_MAX_TOKEN": bool(os.getenv("NEWSBOT_V3_MAX_TOKEN")),
    "NEWSBOT_V3_REAL_SEND": os.getenv("NEWSBOT_V3_REAL_SEND"),
    "NEWSBOT_V3_MOCK_MAX": os.getenv("NEWSBOT_V3_MOCK_MAX"),
    "NEWSBOT_V3_ALLOW_PRODUCTION_CHANNEL": os.getenv("NEWSBOT_V3_ALLOW_PRODUCTION_CHANNEL"),
})
client = MaxClient.from_env(target_channel=os.getenv("NEWSBOT_V3_PRODUCTION_CHANNEL_ID", ""))
print("max_client_diag=", client.diagnostics())
PY

echo
echo "### 13. V3 CONTROLLED SEND CANARY DRY RUN ONLY"
NEWSBOT_V3_PRODUCTION_SEND=true \
NEWSBOT_V3_CUTOVER_CONFIRM=I_UNDERSTAND_V3_SENDS_TO_PRODUCTION \
NEWSBOT_V3_PRODUCTION_CHANNEL_ID="${NEWSBOT_V3_PRODUCTION_CHANNEL_ID:-${CHANNEL_ID:-}}" \
NEWSBOT_V3_TEST_CHANNEL_ID="${NEWSBOT_V3_TEST_CHANNEL_ID:-${CHANNEL_ID:-}}" \
NEWSBOT_MAX_CHANNEL_ID="${NEWSBOT_MAX_CHANNEL_ID:-${CHANNEL_ID:-}}" \
NEWSBOT_V3_ALLOW_PRODUCTION_CHANNEL="${NEWSBOT_V3_ALLOW_PRODUCTION_CHANNEL:-true}" \
NEWSBOT_V3_MAX_TOKEN="${NEWSBOT_V3_MAX_TOKEN:-${MAX_BOT_TOKEN:-}}" \
NEWSBOT_V3_MOCK_MAX="${NEWSBOT_V3_MOCK_MAX:-false}" \
NEWSBOT_V3_REAL_SEND="${NEWSBOT_V3_REAL_SEND:-true}" \
NEWSBOT_V3_MARK_V2_PUBLISHED="${NEWSBOT_V3_MARK_V2_PUBLISHED:-true}" \
"$PY" newsbot_v3/tools/v3_controlled_send_canary.py 2>&1 || true

echo
echo "### 14. V3 HEALTH / PIPELINE DRY TOOLS"
for f in \
  newsbot_v3/tools/v3_healthcheck.py \
  newsbot_v3/tools/v3_dry_run_pipeline.py \
  newsbot_v3/tools/v3_publisher_dry_run.py \
  newsbot_v3/tools/v3_selection_quality_check.py \
  newsbot_v3/tools/v3_seller_output_dry_run.py \
  newsbot_v3/tools/v3_media_pipeline_check.py \
  newsbot_v3/tools/v3_shadow_rehearsal.py
do
  if [ -f "$f" ]; then
    echo "----- $f -----"
    PYTHONPATH=/opt/newsbot_v2/newsbot_v3 "$PY" "$f" 2>&1 || true
  fi
done

echo
echo "### 15. LOG TAILS"
for f in logs/collector.log logs/publisher.log logs/watchdog.log logs/safety_promote.log logs/publisher_v3.log logs/stable_publisher_v3.log; do
  if [ -f "$f" ]; then
    echo "----- $f -----"
    tail -n 80 "$f"
  fi
done
journalctl -u newsbot* --no-pager -n 120 2>/dev/null || true

echo
echo "### 16. FINAL SUMMARY FLAGS"
echo "audit_log=$LOG"
echo "safe_mode=true"
echo "execute_used=false"
echo "finished_at=$(date -Is)"
echo "============================================================"
} 2>&1 | tee "$LOG"

echo "$LOG"
