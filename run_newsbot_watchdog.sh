#!/usr/bin/env bash
set -euo pipefail
cd /opt/newsbot_v2
/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/newsbot_watchdog.py --send
