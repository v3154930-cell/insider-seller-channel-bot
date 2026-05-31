#!/usr/bin/env bash
set -euo pipefail
cd /opt/newsbot_v2
if [ -f /opt/newsbot_v2/.env ]; then
  set -a
  . /opt/newsbot_v2/.env
  set +a
fi
export NEWSBOT_V3_PRODUCTION_SEND=true
export NEWSBOT_V3_REAL_SEND=true
export NEWSBOT_V3_MOCK_MAX=false
export NEWSBOT_V3_CUTOVER_CONFIRM='I_UNDERSTAND_V3_SENDS_TO_PRODUCTION'
export NEWSBOT_V3_PRODUCTION_CHANNEL_ID="${CHANNEL_ID:-${NEWSBOT_V3_PRODUCTION_CHANNEL_ID:-}}"
export NEWSBOT_V3_TEST_CHANNEL_ID="${CHANNEL_ID:-${NEWSBOT_V3_TEST_CHANNEL_ID:-}}"
export NEWSBOT_MAX_CHANNEL_ID="${CHANNEL_ID:-${NEWSBOT_MAX_CHANNEL_ID:-}}"
export NEWSBOT_V3_MAX_TOKEN="${MAX_BOT_TOKEN:-${NEWSBOT_V3_MAX_TOKEN:-}}"
export NEWSBOT_V3_ALLOW_PRODUCTION_CHANNEL=true
export NEWSBOT_V3_MARK_V2_DIGESTED=true
PYTHONPATH=/opt/newsbot_v2/newsbot_v3 /opt/newsbot_v2/venv/bin/python newsbot_v3/tools/v3_digest_send.py --kind final --execute
