#!/usr/bin/env bash
set -euo pipefail

cd /opt/newsbot_v2

/opt/newsbot_v2/venv/bin/python official_channel_collector.py
/opt/newsbot_v2/venv/bin/python official_signal_monitor.py
/opt/newsbot_v2/venv/bin/python signal_monitor.py
/opt/newsbot_v2/venv/bin/python signal_digest.py --publish
/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/admin_alert.py --send || true
