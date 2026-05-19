#!/bin/bash
cd /opt/newsbot_v2 || exit 1
set -a
source /opt/newsbot_v2/.env
set +a

/opt/newsbot_v2/venv/bin/python -m uvicorn admin_app:app --host 0.0.0.0 --port "${ADMIN_PORT:-8088}"
