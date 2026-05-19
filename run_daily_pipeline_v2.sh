#!/bin/bash
cd /opt/newsbot_v2 || exit 1

set -a
source /opt/newsbot_v2/.env
set +a

{
  echo
  echo "===== DAILY PIPELINE START $(date '+%Y-%m-%d %H:%M:%S') ====="
  /opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/daily_pipeline_v2.py
  echo "===== DAILY PIPELINE END $(date '+%Y-%m-%d %H:%M:%S') ====="
  echo
} >> /opt/newsbot_v2/logs/daily_pipeline.log 2>&1
