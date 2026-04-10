#!/bin/bash
cd /opt/newsbot || exit 1
set -a
source /opt/newsbot/.env
set +a
/opt/newsbot/venv/bin/python /opt/newsbot/collector.py >> /opt/newsbot/logs/collector.log 2>&1