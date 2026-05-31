#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests

from app.max_client import MaxClient
from app.visual.mascot_assets import select_mascot_asset, visuals_enabled

AUDIO_DIR = Path('/opt/newsbot_v2/audio_digest/salute')
API_BASE = 'https://platform-api.max.ru'


def _audio_ts_from_name(path: Path) -> datetime | None:
    match = re.match(r'^audio_digest_final_(\d{8})_(\d{6})\.mp3$', path.name)
    if not match:
        return None
    try:
        return datetime.strptime(f"{match.group(1)}{match.group(2)}", "%Y%m%d%H%M%S")
    except ValueError:
        return None


def latest_audio_file() -> Path | None:
    files = list(AUDIO_DIR.glob('audio_digest_final_*.mp3'))
    if not files:
        return None

    def sort_key(path: Path) -> tuple[int, datetime, float]:
        ts = _audio_ts_from_name(path)
        if ts is not None:
            return (1, ts, path.stat().st_mtime)
        return (0, datetime.fromtimestamp(path.stat().st_mtime), path.stat().st_mtime)

    return max(files, key=sort_key)


def ensure_v3_tables(db_path: str) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.executescript("""
CREATE TABLE IF NOT EXISTS send_attempts (id INTEGER PRIMARY KEY, attempt_id TEXT, candidate_id TEXT, sent_at TEXT, status TEXT, error_message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS published_messages (id INTEGER PRIMARY KEY, candidate_id TEXT, message_id TEXT, channel TEXT, published_at TEXT, status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS system_events (id INTEGER PRIMARY KEY, event_id TEXT, event_type TEXT, severity TEXT, message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
""")
        con.commit()
    finally:
        con.close()


def _candidate_id(audio_file: Path | None) -> str:
    if not audio_file:
        return 'audio-digest'
    parts = audio_file.stem.split('_')
    if parts and parts[-1].isdigit() and len(parts[-1]) >= 8:
        return f"audio-digest-{parts[-1][:8]}"
    return 'audio-digest'


def _response_text(resp: requests.Response) -> str:
    return resp.text[:1000]


def _is_attachment_not_ready(status_code: int, response_text: str) -> bool:
    if status_code < 400 or status_code >= 500:
        return False
    t = (response_text or '').lower()
    return any(marker in t for marker in (
        'attachment.not.ready',
        'not.processed',
        'video.not.processed',
    ))


def _audio_mime(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == '.mp3':
        return 'audio/mpeg'
    if suffix == '.wav':
        return 'audio/wav'
    if suffix == '.m4a':
        return 'audio/mp4'
    return 'application/octet-stream'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--v2-db', default='/opt/newsbot_v2/news_queue.db')
    args = ap.parse_args()

    audio_file = latest_audio_file()
    exists = bool(audio_file and audio_file.exists())
    size = audio_file.stat().st_size if exists else 0
    real_send = args.execute
    audio_send_supported = True
    max_audio_message_id = ''
    max_message_id = ''
    send_attempt_recorded = False
    published_message_recorded = False
    production_mutation = False
    send_status = 'dry_run'
    audio_error_class = ''
    audio_error_message = ''
    audio_upload_init_status_code = ''
    audio_upload_init_response_text = ''
    audio_binary_upload_status_code = ''
    audio_binary_upload_response_text = ''
    audio_send_status_code = ''
    audio_send_response_text = ''
    audio_upload_url_present = 'false'
    audio_attachment_payload_shape = ''
    audio_send_attempts = 0
    audio_send_retry_used = 'false'
    audio_send_retry_reason = ''
    audio_send_wait_seconds_total = 0
    audio_send_last_status_code = ''
    audio_send_last_response_text = ''
    visual_assets_enabled = visuals_enabled()
    mascot_asset_kind, mascot_asset_selected = select_mascot_asset(post_kind='audio', audio_digest_kind='audio_digest')
    mascot_attachment_planned = visual_assets_enabled and bool(mascot_asset_selected)
    mascot_send_status = 'dry_run' if (not real_send and mascot_attachment_planned) else 'skipped'

    print(f"audio_file_selected={str(audio_file) if audio_file else ''}")
    print(f"audio_file_exists={'true' if exists else 'false'}")
    print(f"audio_file_size={size}")

    if not real_send:
        print('V3_AUDIO_DIGEST_STATUS=DRY_RUN')
        print('real_send=false')
        print('audio_send_supported=true')
        print('max_audio_message_id=')
        print('max_message_id=')
        print('send_attempt_recorded=false')
        print('published_message_recorded=false')
        print('production_mutation=false')
        print('send_status=dry_run')
        print('audio_error_class=')
        print('audio_error_message=')
        print('audio_upload_init_status_code=')
        print('audio_upload_init_response_text=')
        print('audio_binary_upload_status_code=')
        print('audio_binary_upload_response_text=')
        print('audio_send_status_code=')
        print('audio_send_response_text=')
        print('audio_upload_url_present=false')
        print('audio_attachment_payload_shape=')
        print('audio_send_attempts=0')
        print('audio_send_retry_used=false')
        print('audio_send_retry_reason=')
        print('audio_send_wait_seconds_total=0')
        print('audio_send_last_status_code=')
        print('audio_send_last_response_text=')
        print(f"visual_assets_enabled={str(visual_assets_enabled).lower()}")
        print(f"mascot_asset_selected={mascot_asset_selected if visual_assets_enabled else ''}")
        print(f"mascot_asset_kind={mascot_asset_kind if visual_assets_enabled else ''}")
        print(f"mascot_attachment_planned={str(bool(mascot_attachment_planned)).lower()}")
        print(f"mascot_send_status={mascot_send_status}")
        return 0

    print('real_send=true')

    guard_ok = all([
        os.getenv('NEWSBOT_V3_PRODUCTION_SEND', 'false').lower() == 'true',
        os.getenv('NEWSBOT_V3_REAL_SEND', 'false').lower() == 'true',
        os.getenv('NEWSBOT_V3_MOCK_MAX', 'true').lower() == 'false',
        os.getenv('NEWSBOT_V3_CUTOVER_CONFIRM', '') == 'I_UNDERSTAND_V3_SENDS_TO_PRODUCTION',
        bool(os.getenv('NEWSBOT_V3_PRODUCTION_CHANNEL_ID', '').strip()),
        bool(os.getenv('NEWSBOT_V3_MAX_TOKEN', '').strip()),
    ])
    if not guard_ok:
        print('V3_AUDIO_DIGEST_STATUS=FAIL')
        print('audio_send_supported=true')
        print('max_audio_message_id=')
        print('max_message_id=')
        print('send_attempt_recorded=false')
        print('published_message_recorded=false')
        print('production_mutation=false')
        print('send_status=failed_guard')
        return 1

    if not exists or size <= 0:
        print('V3_AUDIO_DIGEST_STATUS=FAIL')
        print('audio_send_supported=true')
        print('max_audio_message_id=')
        print('max_message_id=')
        print('send_attempt_recorded=false')
        print('published_message_recorded=false')
        print('production_mutation=false')
        print('send_status=failed_missing_audio_file')
        return 1

    channel = os.getenv('NEWSBOT_V3_PRODUCTION_CHANNEL_ID', '').strip()
    os.environ['NEWSBOT_V3_TEST_CHANNEL_ID'] = channel
    os.environ['NEWSBOT_MAX_CHANNEL_ID'] = channel
    client = MaxClient.from_env(target_channel=channel)

    caption = (
        '🎧 <b>Вечерний аудиодайджест Инсайдер Селлер</b>\n\n'
        'Коротко о главных новостях дня и важных сигналах для селлеров.\n\n'
        'ℹ️ Тарифы и расчёты Seller Helper меняются только после проверки официального источника.'
    )

    try:
        init_resp = requests.post(
            f'{API_BASE}/uploads',
            params={'type': 'audio'},
            headers={'Authorization': client.max_token},
            timeout=30,
        )
        audio_upload_init_status_code = str(init_resp.status_code)
        audio_upload_init_response_text = _response_text(init_resp)
        if init_resp.status_code >= 400:
            raise RuntimeError(f'MAX upload init failed: HTTP {init_resp.status_code}')

        try:
            init_data = init_resp.json()
        except Exception as exc:
            raise RuntimeError('MAX upload init failed: invalid JSON response') from exc

        upload_url = init_data.get('url')
        upload_token = init_data.get('token')
        audio_upload_url_present = 'true' if bool(upload_url) else 'false'
        if not upload_url:
            raise RuntimeError('MAX upload init failed: missing upload url')

        with audio_file.open('rb') as f:
            upload_resp = requests.post(
                upload_url,
                files={'data': (audio_file.name, f, _audio_mime(audio_file))},
                timeout=180,
            )
        audio_binary_upload_status_code = str(upload_resp.status_code)
        audio_binary_upload_response_text = _response_text(upload_resp)
        if upload_resp.status_code >= 400:
            raise RuntimeError(f'MAX audio file upload failed: HTTP {upload_resp.status_code}')

        try:
            upload_data = upload_resp.json()
        except Exception:
            upload_data = {}

        final_token = upload_token or upload_data.get('token')
        if not final_token:
            raise RuntimeError('MAX upload failed: missing audio token')

        audio_payload = {'token': final_token}
        attachments = [{'type': 'audio', 'payload': audio_payload}]
        audio_attachment_payload_shape = json.dumps({'attachments_count': 1, 'attachment_type': 'audio', 'payload_keys': sorted(audio_payload.keys())}, ensure_ascii=False, separators=(',', ':'))

        send_payload = {'text': caption, 'format': 'html', 'attachments': attachments}
        send_resp = None
        max_send_attempts = 4
        for attempt in range(1, max_send_attempts + 1):
            audio_send_attempts = attempt
            send_resp = requests.post(
                f'{API_BASE}/messages',
                params={'chat_id': client._coerce_chat_id(channel)},
                headers={'Authorization': client.max_token, 'Content-Type': 'application/json'},
                json=send_payload,
                timeout=30,
            )
            audio_send_status_code = str(send_resp.status_code)
            audio_send_response_text = _response_text(send_resp)
            audio_send_last_status_code = audio_send_status_code
            audio_send_last_response_text = audio_send_response_text

            if send_resp.status_code < 400:
                break

            if _is_attachment_not_ready(send_resp.status_code, audio_send_response_text) and attempt < max_send_attempts:
                audio_send_retry_used = 'true'
                audio_send_retry_reason = 'attachment_not_ready'
                time.sleep(8)
                audio_send_wait_seconds_total += 8
                continue

            raise RuntimeError(f'MAX send audio failed: HTTP {send_resp.status_code}')

        if send_resp is None:
            raise RuntimeError('MAX send audio failed: no response')

        try:
            resp = send_resp.json()
        except Exception as exc:
            raise RuntimeError('MAX send failed: invalid JSON response') from exc

        max_audio_message_id = client.extract_message_id(resp) or ''
        max_message_id = max_audio_message_id
        if not max_message_id:
            send_status = 'failed_missing_message_id'
            raise RuntimeError('missing message id')
        if max_message_id.startswith('mock-msg-'):
            send_status = 'failed_missing_message_id'
            raise RuntimeError('mock message id forbidden in real mode')

        db_path = os.getenv('V3_DB', '/opt/newsbot_v3/runtime/newsbot_v3.db')
        ensure_v3_tables(db_path)
        candidate_id = _candidate_id(audio_file)
        con = sqlite3.connect(db_path)
        try:
            con.execute('INSERT INTO send_attempts(attempt_id,candidate_id,sent_at,status,error_message) VALUES(?,?,?,?,?)', (f'audio-{uuid4().hex[:12]}', candidate_id, datetime.utcnow().isoformat(), 'sent', None))
            con.execute('INSERT INTO published_messages(candidate_id,message_id,channel,published_at,status) VALUES(?,?,?,?,?)', (candidate_id, max_message_id, channel, datetime.utcnow().isoformat(), 'sent'))
            con.commit()
            send_attempt_recorded = True
            published_message_recorded = True
            production_mutation = True
        finally:
            con.close()
        print('V3_AUDIO_DIGEST_STATUS=OK')
        send_status = 'sent'
    except Exception as exc:
        audio_error_class = exc.__class__.__name__
        audio_error_message = str(exc)
        if send_status != 'failed_missing_message_id':
            send_status = 'failed_audio_send'
        print('V3_AUDIO_DIGEST_STATUS=FAIL')

    print('audio_send_supported=true')
    print(f'max_audio_message_id={max_audio_message_id}')
    print(f'max_message_id={max_message_id}')
    print(f"send_attempt_recorded={'true' if send_attempt_recorded else 'false'}")
    print(f"published_message_recorded={'true' if published_message_recorded else 'false'}")
    print(f"production_mutation={'true' if production_mutation else 'false'}")
    print(f'send_status={send_status}')
    print(f'audio_error_class={audio_error_class}')
    print(f'audio_error_message={audio_error_message}')
    print(f'audio_upload_init_status_code={audio_upload_init_status_code}')
    print(f'audio_upload_init_response_text={audio_upload_init_response_text}')
    print(f'audio_binary_upload_status_code={audio_binary_upload_status_code}')
    print(f'audio_binary_upload_response_text={audio_binary_upload_response_text}')
    print(f'audio_send_status_code={audio_send_status_code}')
    print(f'audio_send_response_text={audio_send_response_text}')
    print(f'audio_upload_url_present={audio_upload_url_present}')
    print(f'audio_attachment_payload_shape={audio_attachment_payload_shape}')
    print(f'audio_send_attempts={audio_send_attempts}')
    print(f'audio_send_retry_used={audio_send_retry_used}')
    print(f'audio_send_retry_reason={audio_send_retry_reason}')
    print(f'audio_send_wait_seconds_total={audio_send_wait_seconds_total}')
    print(f'audio_send_last_status_code={audio_send_last_status_code}')
    print(f'audio_send_last_response_text={audio_send_last_response_text}')
    return 0 if send_status == 'sent' else 1


if __name__ == '__main__':
    raise SystemExit(main())
