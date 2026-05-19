import argparse
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import requests

DB_PATH = Path("/opt/newsbot_v2/news_queue.db")
ENV_PATH = Path("/opt/newsbot_v2/.env")
AUDIO_DIR = Path("/opt/newsbot_v2/audio_digest/salute")
API_BASE = "https://platform-api.max.ru"


def load_env():
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def latest_audio_file():
    files = sorted(AUDIO_DIR.glob("audio_digest_salute_*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise RuntimeError("No SaluteSpeech audio files found")
    return files[0]


def audio_mime(audio_path: Path) -> str:
    suffix = audio_path.suffix.lower()
    if suffix == ".mp3":
        return "audio/mpeg"
    if suffix == ".wav":
        return "audio/wav"
    if suffix == ".m4a":
        return "audio/mp4"
    return "application/octet-stream"


def upload_audio(token: str, audio_path: Path):
    print("Requesting MAX audio upload URL...")

    r = requests.post(
        f"{API_BASE}/uploads",
        params={"type": "audio"},
        headers={"Authorization": token},
        timeout=30,
    )

    if r.status_code >= 400:
        raise RuntimeError(f"MAX upload init failed: HTTP {r.status_code}: {r.text[:1000]}")

    data = r.json()
    upload_url = data.get("url")
    upload_token = data.get("token")

    if not upload_url:
        raise RuntimeError(f"No upload url in MAX response: {data}")

    print("Uploading audio file:", audio_path)

    with audio_path.open("rb") as f:
        file_resp = requests.post(
            upload_url,
            files={"data": (audio_path.name, f, audio_mime(audio_path))},
            timeout=180,
        )

    if file_resp.status_code >= 400:
        raise RuntimeError(f"MAX audio file upload failed: HTTP {file_resp.status_code}: {file_resp.text[:1000]}")

    try:
        file_data = file_resp.json()
    except Exception:
        file_data = {}

    final_token = upload_token or file_data.get("token")

    if not final_token:
        raise RuntimeError(f"No audio token after upload. init={data}, upload={file_data}")

    return {"token": final_token}


def send_audio(token: str, channel_id: str, audio_payload: dict):
    try:
        chat_id_value = int(channel_id)
    except Exception:
        chat_id_value = channel_id

    text = (
        "🎧 <b>Вечерний аудиодайджест Инсайдер Селлер</b>\n\n"
        "Коротко о главных новостях дня и важных сигналах для селлеров.\n\n"
        "ℹ️ Тарифы и расчёты Seller Helper меняются только после проверки официального источника."
    )

    payload = {
        "text": text,
        "format": "html",
        "attachments": [
            {
                "type": "audio",
                "payload": audio_payload,
            }
        ],
    }

    last_error = ""

    for attempt in range(1, 8):
        print(f"Sending audio message attempt {attempt}/7...")

        r = requests.post(
            f"{API_BASE}/messages",
            params={"chat_id": chat_id_value},
            headers={
                "Authorization": token,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )

        if r.status_code < 400:
            return r.json()

        last_error = r.text[:1000]
        print(f"MAX send failed: HTTP {r.status_code}: {last_error}")

        if "attachment.not.ready" in r.text or "not.processed" in r.text:
            time.sleep(8)
            continue

        raise RuntimeError(f"MAX send audio failed: HTTP {r.status_code}: {last_error}")

    raise RuntimeError(f"MAX send audio failed after retries: {last_error}")


def ensure_runs_table():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS audio_digest_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        digest_date TEXT,
        audio_path TEXT,
        max_message_id TEXT,
        status TEXT,
        published_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def mark_published(audio_path: Path, result: dict):
    ensure_runs_table()

    try:
        mid = result["message"]["body"]["mid"]
    except Exception:
        mid = ""

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO audio_digest_runs (
            digest_date,
            audio_path,
            max_message_id,
            status
        )
        VALUES (?, ?, ?, 'published')
    """, (
        datetime.now().strftime("%Y-%m-%d"),
        str(audio_path),
        mid,
    ))

    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true", help="Actually publish audio digest to MAX")
    parser.add_argument("--file", help="Specific audio file path")
    args = parser.parse_args()

    load_env()

    token = os.getenv("MAX_BOT_TOKEN")
    channel_id = os.getenv("CHANNEL_ID") or os.getenv("MAX_CHANNEL_ID")

    if not token or not channel_id:
        raise RuntimeError("MAX_BOT_TOKEN or CHANNEL_ID/MAX_CHANNEL_ID not found")

    audio_path = Path(args.file) if args.file else latest_audio_file()

    print("Latest audio:", audio_path)
    print("Size:", audio_path.stat().st_size)

    if not args.publish:
        print("DRY RUN: not published. Use --publish to send to MAX.")
        return

    audio_payload = upload_audio(token, audio_path)
    result = send_audio(token, channel_id, audio_payload)

    print("Published:", result)
    mark_published(audio_path, result)


if __name__ == "__main__":
    main()
