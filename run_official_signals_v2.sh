#!/usr/bin/env bash
set -euo pipefail
cd /opt/newsbot_v2

/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/official_channel_collector.py
/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/official_signal_monitor.py
/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/official_signal_bridge.py
