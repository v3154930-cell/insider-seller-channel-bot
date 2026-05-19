#!/usr/bin/env bash
set -euo pipefail

BASE="/opt/newsbot_v2/audio_digest"
LOG="/opt/newsbot_v2/logs/audio_cleanup.log"

mkdir -p /opt/newsbot_v2/logs

{
  echo "=== audio cleanup $(date '+%Y-%m-%d %H:%M:%S') ==="

  echo "--- delete WAV older than 2 days ---"
  find "$BASE" -type f -name "*.wav" -mtime +2 -print -delete || true

  echo "--- delete temporary mp3 older than 7 days ---"
  find "$BASE" -type f -name "audio_digest_salute_*.mp3" -mtime +7 -print -delete || true

  echo "--- delete final mp3 older than 30 days ---"
  find "$BASE" -type f -name "audio_digest_final_*.mp3" -mtime +30 -print -delete || true

  echo "--- delete empty dirs ---"
  find "$BASE" -type d -empty -print -delete || true

  echo "done"
  echo
} >> "$LOG" 2>&1
