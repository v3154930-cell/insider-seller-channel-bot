#!/usr/bin/env bash
set -euo pipefail
cd /opt/newsbot_v2
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
if [[ -x /opt/newsbot_v2/venv/bin/python ]]; then
  PY=/opt/newsbot_v2/venv/bin/python
else
  PY=python3
fi
exec "$PY" /opt/newsbot_v2/tools/channel_status_check.py \
  --db /opt/newsbot_v2/news_queue.db \
  --collector-log /opt/newsbot_v2/logs/collector.log \
  --publisher-log /opt/newsbot_v2/logs/publisher.log \
  "$@"
