#!/bin/bash
cd /opt/newsbot_v2 || exit 1

set -a
source /opt/newsbot_v2/.env
set +a

{
  echo
  echo "===== WB COMMISSIONS LOADER START $(date '+%Y-%m-%d %H:%M:%S') ====="
  /opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/wb_commissions_loader_v2.py
  echo "===== WB COMMISSIONS LOADER END $(date '+%Y-%m-%d %H:%M:%S') ====="
  echo
} >> /opt/newsbot_v2/logs/wb_commissions_loader.log 2>&1
