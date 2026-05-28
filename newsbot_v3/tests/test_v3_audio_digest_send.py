import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

import tools.v3_audio_digest_send as sut


class Resp:
    def __init__(self, status_code=200, text='', json_data=None, json_exc=None):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data
        self._json_exc = json_exc

    def json(self):
        if self._json_exc:
            raise self._json_exc
        return self._json_data


def _set_real_env(monkeypatch):
    monkeypatch.setenv('NEWSBOT_V3_PRODUCTION_SEND', 'true')
    monkeypatch.setenv('NEWSBOT_V3_REAL_SEND', 'true')
    monkeypatch.setenv('NEWSBOT_V3_MOCK_MAX', 'false')
    monkeypatch.setenv('NEWSBOT_V3_CUTOVER_CONFIRM', 'I_UNDERSTAND_V3_SENDS_TO_PRODUCTION')
    monkeypatch.setenv('NEWSBOT_V3_PRODUCTION_CHANNEL_ID', '123')
    monkeypatch.setenv('NEWSBOT_V3_MAX_TOKEN', 'tok')


def test_dry_run_selects_latest_audio_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    old = tmp_path / 'audio_digest_final_20260526_224501.mp3'
    new = tmp_path / 'audio_digest_final_20260527_224501.mp3'
    old.write_bytes(b'1')
    new.write_bytes(b'22')

    monkeypatch.setattr('sys.argv', ['v3_audio_digest_send.py'])
    rc = sut.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert 'V3_AUDIO_DIGEST_STATUS=DRY_RUN' in out
    assert f'audio_file_selected={new}' in out
    assert 'send_status=dry_run' in out


def test_missing_audio_file_fails_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    _set_real_env(monkeypatch)
    monkeypatch.setattr('sys.argv', ['v3_audio_digest_send.py', '--execute'])
    rc = sut.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert 'V3_AUDIO_DIGEST_STATUS=FAIL' in out
    assert 'send_status=failed_missing_audio_file' in out


def test_real_send_http_error_fails_closed_without_db_writes(tmp_path, monkeypatch, capsys):
    audio = tmp_path / 'audio_digest_final_20260527_224501.mp3'
    audio.write_bytes(b'data')
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    _set_real_env(monkeypatch)
    db = tmp_path / 'v3.db'
    monkeypatch.setenv('V3_DB', str(db))

    monkeypatch.setattr(sut.MaxClient, 'from_env', lambda **kwargs: SimpleNamespace(max_token='tok', extract_message_id=lambda *_: '', _coerce_chat_id=lambda x: int(x)))
    monkeypatch.setattr(sut.requests, 'post', lambda *a, **k: Resp(status_code=500, text='init err', json_data={}))
    monkeypatch.setattr('sys.argv', ['v3_audio_digest_send.py', '--execute'])
    rc = sut.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert 'send_status=failed_audio_send' in out
    assert 'send_attempt_recorded=false' in out
    assert not db.exists()
    assert 'audio_upload_init_status_code=500' in out
    assert 'audio_error_class=RuntimeError' in out


def test_real_send_missing_message_id_fails_closed(tmp_path, monkeypatch, capsys):
    audio = tmp_path / 'audio_digest_final_20260527_224501.mp3'
    audio.write_bytes(b'data')
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    _set_real_env(monkeypatch)

    monkeypatch.setattr(sut.MaxClient, 'from_env', lambda **kwargs: SimpleNamespace(max_token='tok', extract_message_id=lambda *_: '', _coerce_chat_id=lambda x: int(x)))

    def fake_post(url, *args, **kwargs):
        if url.endswith('/uploads'):
            return Resp(status_code=200, text='{}', json_data={'url': 'https://upload', 'token': 'a'})
        if url == 'https://upload':
            return Resp(status_code=200, text='{"token":"b"}', json_data={'token': 'b'})
        return Resp(status_code=200, text='{"ok":true}', json_data={'ok': True})

    monkeypatch.setattr(sut.requests, 'post', fake_post)
    monkeypatch.setattr('sys.argv', ['v3_audio_digest_send.py', '--execute'])
    rc = sut.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert 'send_status=failed_missing_message_id' in out


def test_successful_real_send_writes_runtime_db(tmp_path, monkeypatch, capsys):
    audio = tmp_path / 'audio_digest_final_20260527_224501.mp3'
    audio.write_bytes(b'data')
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    _set_real_env(monkeypatch)
    db = tmp_path / 'v3.db'
    monkeypatch.setenv('V3_DB', str(db))

    monkeypatch.setattr(sut.MaxClient, 'from_env', lambda **kwargs: SimpleNamespace(max_token='tok', extract_message_id=lambda resp: resp['message']['body']['mid'], _coerce_chat_id=lambda x: int(x)))

    def fake_post(url, *args, **kwargs):
        if url.endswith('/uploads'):
            return Resp(status_code=200, text='{"url":"https://upload","token":"a"}', json_data={'url': 'https://upload', 'token': 'a'})
        if url == 'https://upload':
            return Resp(status_code=200, text='{"token":"b"}', json_data={'token': 'b'})
        return Resp(status_code=200, text='{"message":{"body":{"mid":"real-123"}}}', json_data={'message': {'body': {'mid': 'real-123'}}})

    monkeypatch.setattr(sut.requests, 'post', fake_post)
    monkeypatch.setattr('sys.argv', ['v3_audio_digest_send.py', '--execute'])
    rc = sut.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert 'V3_AUDIO_DIGEST_STATUS=OK' in out
    assert 'send_attempt_recorded=true' in out
    assert 'published_message_recorded=true' in out

    con = sqlite3.connect(db)
    try:
        assert con.execute('select count(*) from send_attempts').fetchone()[0] == 1
        assert con.execute('select count(*) from published_messages').fetchone()[0] == 1
    finally:
        con.close()


def test_real_send_rejects_mock_message_id(tmp_path, monkeypatch, capsys):
    audio = tmp_path / 'audio_digest_final_20260527_224501.mp3'
    audio.write_bytes(b'data')
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    _set_real_env(monkeypatch)

    monkeypatch.setattr(sut.MaxClient, 'from_env', lambda **kwargs: SimpleNamespace(max_token='tok', extract_message_id=lambda resp: resp['message_id'], _coerce_chat_id=lambda x: int(x)))
    def fake_post(url, *args, **kwargs):
        if url.endswith('/uploads'):
            return Resp(status_code=200, text='{"url":"https://upload","token":"a"}', json_data={'url': 'https://upload', 'token': 'a'})
        if url == 'https://upload':
            return Resp(status_code=200, text='{"token":"b"}', json_data={'token': 'b'})
        return Resp(status_code=200, text='{"message_id":"mock-msg-abc"}', json_data={'message_id': 'mock-msg-abc'})

    monkeypatch.setattr(sut.requests, 'post', fake_post)
    monkeypatch.setattr('sys.argv', ['v3_audio_digest_send.py', '--execute'])
    rc = sut.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert 'send_status=failed_missing_message_id' in out


def test_latest_audio_prefers_filename_timestamp_over_mtime(tmp_path, monkeypatch):
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    older_name = tmp_path / 'audio_digest_final_20260526_224501.mp3'
    newer_name = tmp_path / 'audio_digest_final_20260527_224501.mp3'
    older_name.write_bytes(b'old')
    newer_name.write_bytes(b'new')

    # Force older filename to have newer mtime: selection must still pick newer timestamp in filename
    newer_name.touch()
    older_name.touch()

    selected = sut.latest_audio_file()
    assert selected == newer_name


def test_binary_upload_http_error_exposes_diagnostics(tmp_path, monkeypatch, capsys):
    audio = tmp_path / 'audio_digest_final_20260527_224501.mp3'
    audio.write_bytes(b'data')
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    _set_real_env(monkeypatch)
    monkeypatch.setattr(sut.MaxClient, 'from_env', lambda **kwargs: SimpleNamespace(max_token='tok', extract_message_id=lambda *_: '', _coerce_chat_id=lambda x: int(x)))

    def fake_post(url, *args, **kwargs):
        if url.endswith('/uploads'):
            return Resp(status_code=200, text='{"url":"https://upload"}', json_data={'url': 'https://upload'})
        return Resp(status_code=500, text='bin err', json_data={})

    monkeypatch.setattr(sut.requests, 'post', fake_post)
    monkeypatch.setattr('sys.argv', ['v3_audio_digest_send.py', '--execute'])
    rc = sut.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert 'audio_binary_upload_status_code=500' in out


def test_message_send_http_error_exposes_diagnostics(tmp_path, monkeypatch, capsys):
    audio = tmp_path / 'audio_digest_final_20260527_224501.mp3'
    audio.write_bytes(b'data')
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    _set_real_env(monkeypatch)
    monkeypatch.setattr(sut.MaxClient, 'from_env', lambda **kwargs: SimpleNamespace(max_token='tok', extract_message_id=lambda *_: '', _coerce_chat_id=lambda x: int(x)))

    def fake_post(url, *args, **kwargs):
        if url.endswith('/uploads'):
            return Resp(status_code=200, text='{"url":"https://upload","token":"a"}', json_data={'url': 'https://upload', 'token': 'a'})
        if url == 'https://upload':
            return Resp(status_code=200, text='ok', json_data={'token': 'a'})
        return Resp(status_code=500, text='send err', json_data={})

    monkeypatch.setattr(sut.requests, 'post', fake_post)
    monkeypatch.setattr('sys.argv', ['v3_audio_digest_send.py', '--execute'])
    rc = sut.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert 'audio_send_status_code=500' in out


def test_invalid_json_exposes_diagnostics(tmp_path, monkeypatch, capsys):
    audio = tmp_path / 'audio_digest_final_20260527_224501.mp3'
    audio.write_bytes(b'data')
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    _set_real_env(monkeypatch)
    monkeypatch.setattr(sut.MaxClient, 'from_env', lambda **kwargs: SimpleNamespace(max_token='tok', extract_message_id=lambda *_: '', _coerce_chat_id=lambda x: int(x)))

    monkeypatch.setattr(sut.requests, 'post', lambda *a, **k: Resp(status_code=200, text='not json', json_exc=ValueError('boom')))
    monkeypatch.setattr('sys.argv', ['v3_audio_digest_send.py', '--execute'])
    rc = sut.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert 'audio_error_message=MAX upload init failed: invalid JSON response' in out


def test_audio_send_retry_then_success_writes_db(tmp_path, monkeypatch, capsys):
    audio = tmp_path / 'audio_digest_final_20260527_224501.mp3'
    audio.write_bytes(b'data')
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    _set_real_env(monkeypatch)
    db = tmp_path / 'v3.db'
    monkeypatch.setenv('V3_DB', str(db))

    monkeypatch.setattr(sut.MaxClient, 'from_env', lambda **kwargs: SimpleNamespace(max_token='tok', extract_message_id=lambda resp: resp['message']['body']['mid'], _coerce_chat_id=lambda x: int(x)))
    monkeypatch.setattr(sut.time, 'sleep', lambda *_: None)

    send_calls = {'n': 0}

    def fake_post(url, *args, **kwargs):
        if url.endswith('/uploads'):
            return Resp(status_code=200, text='{"url":"https://upload","token":"a"}', json_data={'url': 'https://upload', 'token': 'a'})
        if url == 'https://upload':
            return Resp(status_code=200, text='{"token":"b"}', json_data={'token': 'b'})
        send_calls['n'] += 1
        if send_calls['n'] == 1:
            return Resp(status_code=400, text='{"code":"attachment.not.ready","message":"errors.process.attachment.video.not.processed"}', json_data={})
        return Resp(status_code=200, text='{"message":{"body":{"mid":"real-123"}}}', json_data={'message': {'body': {'mid': 'real-123'}}})

    monkeypatch.setattr(sut.requests, 'post', fake_post)
    monkeypatch.setattr('sys.argv', ['v3_audio_digest_send.py', '--execute'])
    rc = sut.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert 'V3_AUDIO_DIGEST_STATUS=OK' in out
    assert 'send_status=sent' in out
    assert 'max_audio_message_id=real-123' in out
    assert 'audio_send_attempts=2' in out
    assert 'audio_send_retry_used=true' in out
    assert 'audio_send_retry_reason=attachment_not_ready' in out
    assert 'audio_send_wait_seconds_total=8' in out

    con = sqlite3.connect(db)
    try:
        assert con.execute('select count(*) from send_attempts').fetchone()[0] == 1
        assert con.execute('select count(*) from published_messages').fetchone()[0] == 1
    finally:
        con.close()


def test_audio_send_retry_exhausted_fails_without_db_writes(tmp_path, monkeypatch, capsys):
    audio = tmp_path / 'audio_digest_final_20260527_224501.mp3'
    audio.write_bytes(b'data')
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    _set_real_env(monkeypatch)
    db = tmp_path / 'v3.db'
    monkeypatch.setenv('V3_DB', str(db))

    monkeypatch.setattr(sut.MaxClient, 'from_env', lambda **kwargs: SimpleNamespace(max_token='tok', extract_message_id=lambda *_: '', _coerce_chat_id=lambda x: int(x)))
    monkeypatch.setattr(sut.time, 'sleep', lambda *_: None)

    def fake_post(url, *args, **kwargs):
        if url.endswith('/uploads'):
            return Resp(status_code=200, text='{"url":"https://upload","token":"a"}', json_data={'url': 'https://upload', 'token': 'a'})
        if url == 'https://upload':
            return Resp(status_code=200, text='{"token":"b"}', json_data={'token': 'b'})
        return Resp(status_code=400, text='{"code":"attachment.not.ready","message":"errors.process.attachment.video.not.processed"}', json_data={})

    monkeypatch.setattr(sut.requests, 'post', fake_post)
    monkeypatch.setattr('sys.argv', ['v3_audio_digest_send.py', '--execute'])
    rc = sut.main()
    out = capsys.readouterr().out

    assert rc == 1
    assert 'V3_AUDIO_DIGEST_STATUS=FAIL' in out
    assert 'send_status=failed_audio_send' in out
    assert 'audio_send_attempts=4' in out
    assert 'audio_send_retry_used=true' in out
    assert 'audio_send_retry_reason=attachment_not_ready' in out
    assert 'audio_send_wait_seconds_total=24' in out
    assert 'send_attempt_recorded=false' in out
    assert 'published_message_recorded=false' in out
    assert not db.exists()


def test_audio_send_non_retryable_400_fails_immediately(tmp_path, monkeypatch, capsys):
    audio = tmp_path / 'audio_digest_final_20260527_224501.mp3'
    audio.write_bytes(b'data')
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    _set_real_env(monkeypatch)

    monkeypatch.setattr(sut.MaxClient, 'from_env', lambda **kwargs: SimpleNamespace(max_token='tok', extract_message_id=lambda *_: '', _coerce_chat_id=lambda x: int(x)))
    monkeypatch.setattr(sut.time, 'sleep', lambda *_: None)

    def fake_post(url, *args, **kwargs):
        if url.endswith('/uploads'):
            return Resp(status_code=200, text='{"url":"https://upload","token":"a"}', json_data={'url': 'https://upload', 'token': 'a'})
        if url == 'https://upload':
            return Resp(status_code=200, text='{"token":"b"}', json_data={'token': 'b'})
        return Resp(status_code=400, text='{"code":"validation.error"}', json_data={})

    monkeypatch.setattr(sut.requests, 'post', fake_post)
    monkeypatch.setattr('sys.argv', ['v3_audio_digest_send.py', '--execute'])
    rc = sut.main()
    out = capsys.readouterr().out

    assert rc == 1
    assert 'audio_send_attempts=1' in out
    assert 'audio_send_retry_used=false' in out
    assert 'audio_send_wait_seconds_total=0' in out


def test_audio_send_success_without_retry_diagnostics(tmp_path, monkeypatch, capsys):
    audio = tmp_path / 'audio_digest_final_20260527_224501.mp3'
    audio.write_bytes(b'data')
    monkeypatch.setattr(sut, 'AUDIO_DIR', tmp_path)
    _set_real_env(monkeypatch)
    db = tmp_path / 'v3.db'
    monkeypatch.setenv('V3_DB', str(db))

    monkeypatch.setattr(sut.MaxClient, 'from_env', lambda **kwargs: SimpleNamespace(max_token='tok', extract_message_id=lambda resp: resp['message']['body']['mid'], _coerce_chat_id=lambda x: int(x)))

    def fake_post(url, *args, **kwargs):
        if url.endswith('/uploads'):
            return Resp(status_code=200, text='{"url":"https://upload","token":"a"}', json_data={'url': 'https://upload', 'token': 'a'})
        if url == 'https://upload':
            return Resp(status_code=200, text='{"token":"b"}', json_data={'token': 'b'})
        return Resp(status_code=200, text='{"message":{"body":{"mid":"real-123"}}}', json_data={'message': {'body': {'mid': 'real-123'}}})

    monkeypatch.setattr(sut.requests, 'post', fake_post)
    monkeypatch.setattr('sys.argv', ['v3_audio_digest_send.py', '--execute'])
    rc = sut.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert 'audio_send_attempts=1' in out
    assert 'audio_send_retry_used=false' in out
    assert 'audio_send_retry_reason=' in out
    assert 'audio_send_wait_seconds_total=0' in out

def test_audio_retry_contract_tokens_present_in_source():
    src = Path(sut.__file__).read_text(encoding='utf-8')
    assert 'audio_send_attempts' in src
    assert 'attachment.not.ready' in src
    assert 'time.sleep(8)' in src
