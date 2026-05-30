#!/usr/bin/env bash
set -euo pipefail

cd /opt/newsbot_v2

LOCK="/tmp/newsbot_v3_audio_digest.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "V3 audio digest already running, exit."
  exit 0
fi

TODAY="$(date +%F)"
MARKER_DIR="/opt/newsbot_v2/data/audio_digest_markers"
MARKER_FILE="${MARKER_DIR}/v3_audio_digest_published_${TODAY}.marker"
mkdir -p "$MARKER_DIR"

if [ -f "$MARKER_FILE" ]; then
  echo "V3 audio digest already published today: ${TODAY}"
  exit 0
fi

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

mkdir -p /opt/newsbot_v2/audio_digest/scripts /opt/newsbot_v2/audio_digest/salute /opt/newsbot_v2/logs

echo "=== v3 audio digest started: $(date) ==="

echo "=== build audio script ==="
/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/audio_digest_story_builder.py

if [ -f /opt/newsbot_v2/audio_digest_text_cleaner.py ]; then
  echo "=== clean audio script ==="
  /opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/audio_digest_text_cleaner.py
else
  echo "audio_digest_text_cleaner.py not found, skip cleaner"
fi

echo "=== synthesize via SaluteSpeech ==="
PYTHONUNBUFFERED=1 timeout 180 /opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/audio_digest_salute.py

LATEST_WAV="$(ls -t /opt/newsbot_v2/audio_digest/salute/audio_digest_salute_*.wav 2>/dev/null | head -1 || true)"
if [ -z "$LATEST_WAV" ] || [ ! -s "$LATEST_WAV" ]; then
  echo "ERROR: no salute wav generated"
  exit 20
fi

MP3="${LATEST_WAV%.wav}.mp3"
echo "=== convert wav to mp3 ==="
ffmpeg -y -i "$LATEST_WAV" -codec:a libmp3lame -b:a 128k "$MP3"

if [ ! -s "$MP3" ]; then
  echo "ERROR: mp3 conversion failed: $MP3"
  exit 21
fi

echo "=== mix radio stinger ==="
/opt/newsbot_v2/mix_audio_digest_stinger.sh "$MP3"

FINAL="$(ls -t /opt/newsbot_v2/audio_digest/salute/audio_digest_final_*.mp3 2>/dev/null | head -1 || true)"
if [ -z "$FINAL" ] || [ ! -s "$FINAL" ]; then
  echo "ERROR: no final audio mp3 generated"
  exit 22
fi

echo "Latest final audio: $FINAL"
ls -lh "$FINAL"

echo "=== send via v3 MAX audio sender ==="
/opt/newsbot_v2/venv/bin/python -u /opt/newsbot_v2/newsbot_v3/tools/v3_audio_digest_send.py --execute

echo "published_at=$(date -Is)" > "$MARKER_FILE"
echo "final_audio=$FINAL" >> "$MARKER_FILE"
echo "V3 audio digest marker written: $MARKER_FILE"

echo "=== v3 audio digest finished: $(date) ==="
