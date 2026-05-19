import os
import re
import ssl
import uuid
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

import requests

DB_PATH = Path("/opt/newsbot_v2/news_queue.db")
ENV_PATH = Path("/opt/newsbot_v2/.env")
OUT_DIR = Path("/opt/newsbot_v2/audio_digest/salute")

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
SYNTH_URL = "https://smartspeech.sber.ru/rest/v1/text:synthesize"


def load_env():
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_latest_script():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    row = cur.execute("""
        SELECT id, script_text, script_path, created_at
        FROM audio_digest_scripts
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    conn.close()

    if not row:
        raise RuntimeError("No audio digest script found. Run audio_digest_story_builder.py first.")

    return dict(row)


def trim_for_salute(text: str, limit=3900) -> str:
    text = text or ""
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) <= limit:
        return text

    text = text[:limit].rstrip()
    cut = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
    if cut > 1000:
        text = text[:cut + 1]

    return text


def get_access_token():
    auth_key = os.getenv("SALUTE_SPEECH_AUTH_KEY", "").strip()
    scope = os.getenv("SALUTE_SPEECH_SCOPE", "SALUTE_SPEECH_PERS").strip()

    if not auth_key or auth_key == "PASTE_AUTHORIZATION_KEY_HERE":
        raise RuntimeError(
            "SALUTE_SPEECH_AUTH_KEY is not set. Add Authorization Key to /opt/newsbot_v2/.env"
        )

    headers = {
        "Authorization": f"Basic {auth_key}",
        "RqUID": str(uuid.uuid4()),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    data = {
        "scope": scope,
    }

    verify_ssl = os.getenv("SALUTE_SPEECH_VERIFY_SSL", "true").lower() not in ("0", "false", "no")

    resp = requests.post(
        OAUTH_URL,
        headers=headers,
        data=data,
        timeout=30,
        verify=verify_ssl,
    )

    if resp.status_code >= 400:
        raise RuntimeError(f"OAuth failed: HTTP {resp.status_code}: {resp.text[:1000]}")

    payload = resp.json()
    token = payload.get("access_token")

    if not token:
        raise RuntimeError(f"access_token not found in OAuth response: {payload}")

    return token


def synthesize(text: str, out_path: Path):
    token = get_access_token()

    voice = os.getenv("SALUTE_SPEECH_VOICE", "Bys_24000").strip()
    audio_format = os.getenv("SALUTE_SPEECH_FORMAT", "wav16").strip()

    params = {
        "format": audio_format,
        "voice": voice,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/text",
    }

    verify_ssl = os.getenv("SALUTE_SPEECH_VERIFY_SSL", "true").lower() not in ("0", "false", "no")

    resp = requests.post(
        SYNTH_URL,
        params=params,
        headers=headers,
        data=text.encode("utf-8"),
        timeout=120,
        verify=verify_ssl,
    )

    if resp.status_code >= 400:
        raise RuntimeError(f"Synthesis failed: HTTP {resp.status_code}: {resp.text[:1000]}")

    out_path.write_bytes(resp.content)
    return out_path


def main():
    load_env()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    script = get_latest_script()
    text = trim_for_salute(script["script_text"])

    ext = "wav" if os.getenv("SALUTE_SPEECH_FORMAT", "wav16").startswith("wav") else "audio"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"audio_digest_salute_{ts}.{ext}"

    print("=== latest script ===")
    print("script_id:", script["id"])
    print("script_path:", script["script_path"])
    print("chars:", len(text))
    print()
    print(text)
    print()
    print("=== synthesize ===")
    print("voice:", os.getenv("SALUTE_SPEECH_VOICE", "Bys_24000"))
    print("format:", os.getenv("SALUTE_SPEECH_FORMAT", "wav16"))
    print("out:", out_path)

    synthesize(text, out_path)

    print("OK: audio generated")
    print("file:", out_path)
    print("size:", out_path.stat().st_size)


if __name__ == "__main__":
    main()
