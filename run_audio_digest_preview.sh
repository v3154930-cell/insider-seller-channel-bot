#!/usr/bin/env bash
set -euo pipefail

cd /opt/newsbot_v2

echo "=== audio digest preview started: $(date) ==="

echo
echo "=== BUILD SCRIPT ==="
/opt/newsbot_v2/venv/bin/python audio_digest_story_builder.py

echo
echo "=== CLEAN SCRIPT ==="
/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/audio_digest_text_cleaner.py

LATEST_SCRIPT=$(ls -t /opt/newsbot_v2/audio_digest/scripts/audio_digest_script_*.txt | head -1)

echo
echo "=== LATEST SCRIPT PATH ==="
echo "$LATEST_SCRIPT"

echo
echo "=== LATEST SCRIPT TEXT ==="
cat "$LATEST_SCRIPT"

echo
echo "=== BAD PHRASES CHECK ==="
grep -niE "что проверить|проверьте|проверить селлеру|операционные действия|сЭллерская|СЭллерская" "$LATEST_SCRIPT" || echo "bad phrases not found"

echo
echo "=== audio digest preview finished: $(date) ==="
