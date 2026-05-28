import pytest

from app.max_client import MaxClient, MaxClientGuardError, MaxClientSendError


class _Resp:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data
        self.text = text

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


def _client():
    return MaxClient(
        mock_mode=False,
        real_send_enabled=True,
        target_channel="ch-test",
        test_channel_id="ch-test",
        allow_production_channel=False,
        production_channel_id="",
        max_token="token-1",
    )


def test_send_text_real_mode_posts_expected_payload(monkeypatch):
    calls = {}

    def fake_post(url, params, json, headers, timeout):
        calls.update({"url": url, "params": params, "json": json, "headers": headers, "timeout": timeout})
        return _Resp(data={"message": {"body": {"mid": "mid-123"}}})

    monkeypatch.setattr("app.max_client.requests.post", fake_post)
    resp = _client().send_text("123", "hello")

    assert resp["message"]["body"]["mid"] == "mid-123"
    assert calls["url"] == "https://platform-api.max.ru/messages"
    assert calls["params"] == {"chat_id": 123}
    assert calls["headers"]["Authorization"] == "token-1"
    assert calls["json"]["format"] == "html"


def test_send_text_with_callback_posts_inline_keyboard(monkeypatch):
    calls = {}

    def fake_post(url, params, json, headers, timeout):
        calls["json"] = json
        return _Resp(data={"id": "real-1"})

    monkeypatch.setattr("app.max_client.requests.post", fake_post)
    resp = _client().send_text_with_callback_button("abc", "t", "btn", "full_article:1")

    assert resp["id"] == "real-1"
    btn = calls["json"]["attachments"][0]["payload"]["buttons"][0][0]
    assert btn == {"type": "callback", "text": "btn", "payload": "full_article:1"}
    assert "url" not in btn
    assert "link" not in btn


def test_real_mode_http_error_fails_closed(monkeypatch):
    monkeypatch.setattr("app.max_client.requests.post", lambda *args, **kwargs: _Resp(status_code=500, text="err", data={}))
    with pytest.raises(MaxClientSendError):
        _client().send_text("123", "hello")


def test_real_mode_missing_message_id_fails_closed(monkeypatch):
    monkeypatch.setattr("app.max_client.requests.post", lambda *args, **kwargs: _Resp(data={"ok": True}))
    with pytest.raises(MaxClientSendError):
        _client().send_text("123", "hello")


def test_real_mode_guard_failure_raises_guard_error():
    c = _client()
    c.target_channel = "different"
    with pytest.raises(MaxClientGuardError):
        c.send_text("123", "hello")


def test_extract_message_id_variants():
    c = _client()
    assert c.extract_message_id({"message": {"body": {"mid": "a"}}}) == "a"
    assert c.extract_message_id({"message": {"id": "b"}}) == "b"
    assert c.extract_message_id({"message_id": "c"}) == "c"
    assert c.extract_message_id({"id": "d"}) == "d"
    assert c.extract_message_id({"mid": "e"}) == "e"
