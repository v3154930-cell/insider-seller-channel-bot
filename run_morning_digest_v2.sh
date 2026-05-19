#!/bin/bash
cd /opt/newsbot_v2 || exit 1
set -a
source /opt/newsbot_v2/.env
set +a
/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/digest_v2.py morning --send >> /opt/newsbot_v2/logs/digest.log 2>&1
