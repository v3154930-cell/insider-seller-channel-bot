#!/usr/bin/env bash
set -u

cd /opt/newsbot_v2 || exit 1

LOG="/opt/newsbot_v2/logs/yandex_tariff_clean_refresh.log"
DB="/opt/newsbot_v2/data/unified_tariffs.db"
BACKUP_DIR="/opt/newsbot_v2/backups"

mkdir -p "$BACKUP_DIR" /opt/newsbot_v2/logs

{
  echo
  echo "===== YANDEX TARIFF CLEAN REFRESH START $(date '+%Y-%m-%d %H:%M:%S') ====="

  BEFORE="$(sqlite3 "$DB" "
    SELECT COUNT(*) || '|' || COALESCE(MAX(created_at),'') || '|' || COALESCE(MAX(valid_from),'')
    FROM clean_commissions
    WHERE marketplace='yandex' AND fee_type='commission_only';
  ")"

  echo "BEFORE: $BEFORE"

  cp -a "$DB" "$BACKUP_DIR/unified_tariffs.before_yandex_clean_refresh.$(date '+%Y%m%d_%H%M%S').db"

  /opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/import_yandex_api_commissions_to_clean.py

  AFTER="$(sqlite3 "$DB" "
    SELECT COUNT(*) || '|' || COALESCE(MAX(created_at),'') || '|' || COALESCE(MAX(valid_from),'')
    FROM clean_commissions
    WHERE marketplace='yandex' AND fee_type='commission_only';
  ")"

  echo "AFTER: $AFTER"

  if [ "$BEFORE" != "$AFTER" ]; then
    echo "Yandex clean_commissions changed. Restart helperbot.service"
    systemctl restart helperbot.service
    sleep 3
    systemctl is-active helperbot.service
  else
    echo "Yandex clean_commissions unchanged. Helper restart skipped."
  fi

  echo "===== YANDEX TARIFF CLEAN REFRESH END $(date '+%Y-%m-%d %H:%M:%S') ====="
} >> "$LOG" 2>&1

tail -120 "$LOG"
