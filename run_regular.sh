#!/bin/bash
cd /opt/newsbot || exit 1
set -a
source /opt/newsbot/.env
set +a
/opt/newsbot/venv/bin/python /opt/newsbot/publisher.py --mode=regular >> /opt/newsbot/logs/publisher.log 2>&1