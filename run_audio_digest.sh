#!/usr/bin/env bash
set -euo pipefail

cd /opt/newsbot_v2

LOCK="/tmp/newsbot_audio_digest.lock"
TODAY="$(date +%F)"

exec 9>"$LOCK"
if ! flock -n 9; then
  echo "Audio digest already running, exit."
  exit 0
fi

# Защита от дублей: если сегодня уже был опубликован аудиодайджест, не публикуем повторно.
if sqlite3 news_queue.db "SELECT COUNT(*) FROM audio_digest_runs WHERE digest_date='${TODAY}' AND status='published';" | grep -qv '^0$'; then
  echo "Audio digest already published today: ${TODAY}"
  exit 0
fi

echo "=== audio digest started: $(date) ==="

# 1. Собираем сценарий дайджеста
/opt/newsbot_v2/venv/bin/python audio_digest_story_builder.py

echo "=== clean audio script ==="
/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/audio_digest_text_cleaner.py

# 2. Озвучиваем через SaluteSpeech
PYTHONUNBUFFERED=1 timeout 180 /opt/newsbot_v2/venv/bin/python audio_digest_salute.py

# 3. Конвертируем свежий WAV в MP3
LATEST_WAV=$(ls -t audio_digest/salute/audio_digest_salute_*.wav | head -1)
MP3="${LATEST_WAV%.wav}.mp3"

ffmpeg -y -i "$LATEST_WAV" -codec:a libmp3lame -b:a 128k "$MP3"

# 4. Накладываем радионовостную отбивку
./mix_audio_digest_stinger.sh "$MP3"

# 5. Публикуем финальный MP3 в MAX
FINAL=$(ls -t audio_digest/salute/audio_digest_final_*.mp3 | head -1)

/opt/newsbot_v2/venv/bin/python audio_digest_max_publisher.py --publish --file "$FINAL"

echo "=== audio digest finished: $(date) ==="
