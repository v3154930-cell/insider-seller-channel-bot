#!/usr/bin/env bash
set -euo pipefail
cd /opt/newsbot_v2

if [ -f /opt/newsbot_v2/.env ]; then
  set -a
  . /opt/newsbot_v2/.env
  set +a
fi

export PYTHONPATH=/opt/newsbot_v2:/opt/newsbot_v2/newsbot_v3
exec /opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/collector_v2.py
