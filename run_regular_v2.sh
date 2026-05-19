#!/bin/bash
cd /opt/newsbot_v2 || exit 1
set -a
source /opt/newsbot_v2/.env
set +a
/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/publisher_v2.py >> /opt/newsbot_v2/logs/publisher.log 2>&1
