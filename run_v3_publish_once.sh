#!/usr/bin/env bash
set -euo pipefail
cd /opt/newsbot_v2

if [ -f /opt/newsbot_v2/.env ]; then
  set -a
  . /opt/newsbot_v2/.env
  set +a
fi

export PYTHONPATH=/opt/newsbot_v2/newsbot_v3:/opt/newsbot_v2
export NEWSBOT_V3_PRODUCTION_SEND=true
export NEWSBOT_V3_REAL_SEND=true
export NEWSBOT_V3_MOCK_MAX=false
export NEWSBOT_V3_CUTOVER_CONFIRM='I_UNDERSTAND_V3_SENDS_TO_PRODUCTION'
export NEWSBOT_V3_PRODUCTION_CHANNEL_ID="${CHANNEL_ID:-${NEWSBOT_V3_PRODUCTION_CHANNEL_ID:-}}"
export NEWSBOT_V3_TEST_CHANNEL_ID="${CHANNEL_ID:-${NEWSBOT_V3_TEST_CHANNEL_ID:-}}"
export NEWSBOT_MAX_CHANNEL_ID="${CHANNEL_ID:-${NEWSBOT_MAX_CHANNEL_ID:-}}"
export NEWSBOT_V3_MAX_TOKEN="${MAX_BOT_TOKEN:-${NEWSBOT_V3_MAX_TOKEN:-}}"
export NEWSBOT_V3_ALLOW_PRODUCTION_CHANNEL=true
export NEWSBOT_V3_MARK_V2_PUBLISHED=true
export NEWSBOT_V3_MAX_CANDIDATE_ATTEMPTS_PER_RUN=10
export NEWSBOT_V3_SEND_MASCOT_ATTACHMENTS=false

/opt/newsbot_v2/venv/bin/python -c "import sqlite3; con=sqlite3.connect('/opt/newsbot_v2/news_queue.db'); cur=con.execute(\"UPDATE news SET seller_decision='digest' WHERE seller_decision='publish' AND COALESCE(is_published,0)=0 AND COALESCE(max_message_id,'')='' AND (COALESCE(seller_relevance_score,0)<5 OR COALESCE(actionability_score,0)<5)\"); con.commit(); print('preflight_demoted_weak_publish=',cur.rowcount); con.close()"

/opt/newsbot_v2/venv/bin/python newsbot_v3/tools/v3_controlled_send_canary.py --execute
