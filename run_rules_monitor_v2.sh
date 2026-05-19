#!/bin/bash
cd /opt/newsbot_v2 || exit 1
set -a
source /opt/newsbot_v2/.env
set +a

{
  echo "===== RULES MONITOR START $(date '+%Y-%m-%d %H:%M:%S') ====="
  /opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/rules_monitor_v2.py
  /opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/classify_rules_signals_v2.py
  /opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/rules_digest_preview_v2.py
  echo "===== RULES MONITOR END $(date '+%Y-%m-%d %H:%M:%S') ====="
  echo
} >> /opt/newsbot_v2/logs/rules_monitor.log 2>&1
