#!/bin/bash
cd /opt/newsbot_v2 || exit 1

set -a
source /opt/newsbot_v2/.env
set +a

{
  echo
  echo "===== YANDEX RULES LOADER START $(date '+%Y-%m-%d %H:%M:%S') ====="
  /opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/yandex_rules_loader_v2.py
  echo "===== YANDEX RULES LOADER END $(date '+%Y-%m-%d %H:%M:%S') ====="
  echo
} >> /opt/newsbot_v2/logs/yandex_rules_loader.log 2>&1
