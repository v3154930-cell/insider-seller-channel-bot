#!/usr/bin/env bash
set -euo pipefail

cd /opt/newsbot_v2

STINGER="audio_digest/assets/radio_stinger.mp3"
VOICE_MP3="${1:-}"

if [ ! -f "$STINGER" ]; then
  echo "ERROR: stinger not found: $STINGER"
  exit 1
fi

if [ -z "$VOICE_MP3" ]; then
  VOICE_MP3=$(ls -t audio_digest/salute/audio_digest_salute_*.mp3 | head -1)
fi

if [ ! -f "$VOICE_MP3" ]; then
  echo "ERROR: voice mp3 not found: $VOICE_MP3"
  exit 1
fi

OUT="audio_digest/salute/audio_digest_final_$(date +%Y%m%d_%H%M%S).mp3"

ffmpeg -y \
  -i "$VOICE_MP3" \
  -i "$STINGER" \
  -filter_complex "\
[0:a]aformat=sample_rates=24000:channel_layouts=mono[voice];\
[1:a]aformat=sample_rates=24000:channel_layouts=mono,aloop=loop=-1:size=100000000,atrim=0:8,asetpts=N/SR/TB,afade=t=in:st=0:d=0.2,afade=t=out:st=5.5:d=2.5,volume=0.12[bed];\
[voice][bed]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[out]" \
  -map "[out]" \
  -codec:a libmp3lame \
  -b:a 128k \
  "$OUT"

echo "OK: final audio created"
ls -lh "$VOICE_MP3" "$STINGER" "$OUT"
echo "$OUT"
