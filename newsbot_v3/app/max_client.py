from __future__ import annotations

import os
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Any, Optional

import requests


class MaxClientGuardError(RuntimeError):
    pass


class MaxClientSendError(RuntimeError):
    pass


@dataclass
class MaxClient:
    mock_mode: bool = True
    real_send_enabled: bool = False
    target_channel: str = ""
    test_channel_id: str = ""
    allow_production_channel: bool = False
    production_channel_id: str = ""
    max_token: str = ""

    @classmethod
    def from_env(cls, target_channel: str = "") -> "MaxClient":
        real_send_enabled = os.getenv("NEWSBOT_V3_REAL_SEND", "false").lower() == "true"
        mock_mode = os.getenv("NEWSBOT_V3_MOCK_MAX", "true").lower() == "true"
        test_channel_id = os.getenv("NEWSBOT_V3_TEST_CHANNEL_ID", "").strip()
        allow_production_channel = os.getenv("NEWSBOT_V3_ALLOW_PRODUCTION_CHANNEL", "false").lower() == "true"
        production_channel_id = (
            os.getenv("NEWSBOT_V3_PRODUCTION_CHANNEL_ID", "").strip()
            or os.getenv("NEWSBOT_MAX_CHANNEL_ID", "").strip()
        )
        max_token = os.getenv("NEWSBOT_V3_MAX_TOKEN", "").strip()
        return cls(
            mock_mode=mock_mode,
            real_send_enabled=real_send_enabled,
            target_channel=target_channel,
            test_channel_id=test_channel_id,
            allow_production_channel=allow_production_channel,
            production_channel_id=production_channel_id,
            max_token=max_token,
        )

    def diagnostics(self) -> dict[str, Any]:
        guard = self._guard_ok()
        mode = "mock" if self.mock_mode and not self.real_send_enabled else ("limited_live" if guard else "blocked")
        return {
            "max_mode": mode,
            "max_guard_ok": guard,
            "real_send_enabled": self.real_send_enabled,
            "target_channel": self.target_channel,
            "test_channel_guard": guard,
        }

    def _msg_id(self, *parts: str) -> str:
        digest = sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]
        return f"mock-msg-{digest}"

    def _resp(self, kind: str, target: str, payload: str = "") -> dict[str, Any]:
        return {"ok": True, "kind": kind, "target": target, "message_id": self._msg_id(kind, target, payload)}

    def _guard_ok(self) -> bool:
        if not self.real_send_enabled or self.mock_mode:
            return False
        if not self.target_channel:
            return False
        target_is_test = bool(self.test_channel_id) and self.target_channel == self.test_channel_id
        target_is_allowed_production = (
            bool(self.production_channel_id)
            and self.target_channel == self.production_channel_id
            and self.allow_production_channel
        )
        if not (target_is_test or target_is_allowed_production):
            return False
        if not self.max_token:
            return False
        return True

    def _send_real_visible_message(self, target: str, text: str) -> dict[str, Any]:
        if not self._guard_ok():
            raise MaxClientGuardError("Real send blocked by v3 test-channel guard.")
        return self._send_max_message(target=target, text=text)

    def _coerce_chat_id(self, channel_id: str) -> Any:
        try:
            return int(channel_id)
        except Exception:
            return channel_id

    def _send_max_message(self, target: str, text: str, attachments: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
        url = "https://platform-api.max.ru/messages"
        payload: dict[str, Any] = {"text": text, "format": "html"}
        if attachments:
            payload["attachments"] = attachments
        try:
            response = requests.post(
                url,
                params={"chat_id": self._coerce_chat_id(target)},
                json=payload,
                headers={"Authorization": self.max_token, "Content-Type": "application/json"},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise MaxClientSendError(f"MAX send failed: request error: {exc}") from exc
        if response.status_code >= 400:
            raise MaxClientSendError(f"MAX send failed: HTTP {response.status_code}: {response.text[:1000]}")
        try:
            data = response.json()
        except Exception as exc:
            raise MaxClientSendError(f"MAX send failed: invalid JSON response: {response.text[:1000]}") from exc
        msg_id = self.extract_message_id(data)
        if not msg_id:
            raise MaxClientSendError(f"MAX send failed: missing message id: {str(data)[:1000]}")
        return data


    def _extract_upload_token(self, *payloads: dict[str, Any]) -> str:
        """Extract MAX upload token from known and nested upload response shapes.

        Image upload currently returns:
        {"photos": {"<photo_id>": {"token": "..."}}}

        Audio upload usually returns token directly either from init or upload response.
        Keep this recursive and conservative so both formats work.
        """
        def walk(value: Any) -> str:
            if isinstance(value, dict):
                for key in ("token", "upload_token", "attachment_token"):
                    token = value.get(key)
                    if token:
                        return str(token)

                # Known wrappers first.
                for key in ("photo", "photos", "image", "images", "attachment", "attachments", "payload", "result", "data"):
                    nested = value.get(key)
                    token = walk(nested)
                    if token:
                        return token

                # Fallback for dynamic ids, for example photos["<id>"]["token"].
                for nested in value.values():
                    token = walk(nested)
                    if token:
                        return token

            elif isinstance(value, list):
                for item in value:
                    token = walk(item)
                    if token:
                        return token

            return ""

        for payload in payloads:
            token = walk(payload)
            if token:
                return token
        return ""

    def _image_mime(self, file_path: str) -> str:
        suffix = Path(file_path).suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".png":
            return "image/png"
        if suffix == ".webp":
            return "image/webp"
        return "application/octet-stream"

    def _upload_image(self, file_path: str) -> dict[str, Any]:
        try:
            init = requests.post(
                "https://platform-api.max.ru/uploads",
                params={"type": "image"},
                headers={"Authorization": self.max_token},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise MaxClientSendError(f"MAX image upload init failed: request error: {exc}") from exc
        if init.status_code >= 400:
            raise MaxClientSendError(f"MAX image upload init failed: HTTP {init.status_code}: {init.text[:1000]}")
        try:
            data = init.json()
        except Exception as exc:
            raise MaxClientSendError(f"MAX image upload init failed: invalid JSON response: {init.text[:1000]}") from exc

        upload_url = data.get("url") or data.get("upload_url")
        init_token = self._extract_upload_token(data)
        if not upload_url:
            raise MaxClientSendError("MAX image upload init failed: missing upload url")

        with open(file_path, "rb") as f:
            try:
                up = requests.post(
                    upload_url,
                    files={"data": (Path(file_path).name, f, self._image_mime(file_path))},
                    timeout=180,
                )
            except requests.RequestException as exc:
                raise MaxClientSendError(f"MAX image file upload failed: request error: {exc}") from exc
        if up.status_code >= 400:
            raise MaxClientSendError(f"MAX image file upload failed: HTTP {up.status_code}: {up.text[:1000]}")
        try:
            up_data = up.json()
        except Exception:
            up_data = {}

        final_token = self._extract_upload_token(up_data, data) or init_token
        if not final_token:
            raise MaxClientSendError("MAX image upload failed: missing image token")
        return {"token": final_token}

    def _audio_mime(self, file_path: str) -> str:
        suffix = Path(file_path).suffix.lower()
        if suffix == ".mp3":
            return "audio/mpeg"
        if suffix == ".wav":
            return "audio/wav"
        if suffix == ".m4a":
            return "audio/mp4"
        return "application/octet-stream"

    def _upload_audio(self, file_path: str) -> dict[str, Any]:
        init = requests.post(
            "https://platform-api.max.ru/uploads",
            params={"type": "audio"},
            headers={"Authorization": self.max_token},
            timeout=30,
        )
        if init.status_code >= 400:
            raise MaxClientSendError(f"MAX upload init failed: HTTP {init.status_code}: {init.text[:1000]}")
        try:
            data = init.json()
        except Exception as exc:
            raise MaxClientSendError("MAX upload init failed: invalid JSON response") from exc

        upload_url = data.get("url")
        upload_token = data.get("token")
        if not upload_url:
            raise MaxClientSendError("MAX upload init failed: missing upload url")

        with open(file_path, "rb") as f:
            up = requests.post(
                upload_url,
                files={"data": (Path(file_path).name, f, self._audio_mime(file_path))},
                timeout=180,
            )
        if up.status_code >= 400:
            raise MaxClientSendError(f"MAX audio file upload failed: HTTP {up.status_code}: {up.text[:1000]}")
        try:
            up_data = up.json()
        except Exception:
            up_data = {}

        final_token = upload_token or up_data.get("token")
        if not final_token:
            raise MaxClientSendError("MAX upload failed: missing audio token")
        return {"token": final_token}

    def send_text(self, channel_id: str, text: str) -> dict[str, Any]:
        if self.real_send_enabled and not self.mock_mode:
            if not self._guard_ok():
                raise MaxClientGuardError("Real send blocked by v3 test-channel guard.")
            return self._send_max_message(target=channel_id, text=text)
        return self._resp("text", channel_id, text)

    def send_text_with_callback_button(self, channel_id: str, text: str, button_text: str, callback_payload: str) -> dict[str, Any]:
        if self.real_send_enabled and not self.mock_mode:
            if not self._guard_ok():
                raise MaxClientGuardError("Real send blocked by v3 test-channel guard.")
            attachments = [
                {
                    "type": "inline_keyboard",
                    "payload": {
                        "buttons": [[{"type": "callback", "text": button_text, "payload": callback_payload}]],
                    },
                }
            ]
            return self._send_max_message(target=channel_id, text=text, attachments=attachments)
        return {**self._resp("text_callback", channel_id, f"{text}:{callback_payload}"), "button_text": button_text, "callback_payload": callback_payload, "external_url_button_used": False}

    def send_text_with_image(self, channel_id: str, text: str, image_path: str) -> dict[str, Any]:
        if self.real_send_enabled and not self.mock_mode:
            if not self._guard_ok():
                raise MaxClientGuardError("Real send blocked by v3 test-channel guard.")
            image_payload = self._upload_image(image_path)
            attachments = [{"type": "image", "payload": image_payload}]
            return self._send_max_message(target=channel_id, text=text, attachments=attachments)
        return {**self._resp("text_image", channel_id, f"{text}:{image_path}"), "image_path": image_path}

    def send_text_with_callback_button_and_image(
        self,
        channel_id: str,
        text: str,
        button_text: str,
        callback_payload: str,
        image_path: str,
    ) -> dict[str, Any]:
        if self.real_send_enabled and not self.mock_mode:
            if not self._guard_ok():
                raise MaxClientGuardError("Real send blocked by v3 test-channel guard.")
            image_payload = self._upload_image(image_path)
            attachments = [
                {"type": "image", "payload": image_payload},
                {
                    "type": "inline_keyboard",
                    "payload": {
                        "buttons": [[{"type": "callback", "text": button_text, "payload": callback_payload}]],
                    },
                },
            ]
            return self._send_max_message(target=channel_id, text=text, attachments=attachments)
        return {
            **self._resp("text_callback_image", channel_id, f"{text}:{callback_payload}:{image_path}"),
            "button_text": button_text,
            "callback_payload": callback_payload,
            "external_url_button_used": False,
            "image_path": image_path,
        }

    def send_text_with_url_button(self, channel_id: str, text: str, button_text: str, url: str) -> dict[str, Any]:
        if self.real_send_enabled and not self.mock_mode:
            if not self._guard_ok():
                raise MaxClientGuardError("Real send blocked by v3 test-channel guard.")
            attachments = [
                {
                    "type": "inline_keyboard",
                    "payload": {
                        "buttons": [[{"type": "link", "text": button_text, "url": url}]],
                    },
                }
            ]
            return self._send_max_message(target=channel_id, text=text, attachments=attachments)
        return {
            **self._resp("text_url", channel_id, f"{text}:{url}"),
            "button_text": button_text,
            "url": url,
            "external_url_button_used": True,
        }

    def send_audio(self, channel_id: str, file_path: str, caption: str) -> dict[str, Any]:
        if self.real_send_enabled and not self.mock_mode:
            if not self._guard_ok():
                raise MaxClientGuardError("Real send blocked by v3 test-channel guard.")
            audio_payload = self._upload_audio(file_path)
            attachments = [{"type": "audio", "payload": audio_payload}]
            return self._send_max_message(target=channel_id, text=caption, attachments=attachments)
        return self._resp("audio", channel_id, f"{file_path}:{caption}")

    def send_visible_message(self, target: str, text: str) -> dict[str, Any]:
        if self.mock_mode or not self.real_send_enabled:
            return self._resp("visible", target, text)
        return self._send_real_visible_message(target, text)

    def answer_callback(self, callback_id: str, text: Optional[str] = None) -> dict[str, Any]:
        return {"ok": True, "callback_id": callback_id, "text": text}

    def extract_message_id(self, response: dict[str, Any]) -> Optional[str]:
        message = response.get("message")
        if isinstance(message, dict):
            body = message.get("body")
            if isinstance(body, dict) and body.get("mid"):
                return str(body.get("mid"))
            if message.get("id"):
                return str(message.get("id"))
        for key in ("message_id", "id", "mid"):
            value = response.get(key)
            if value:
                return str(value)
        return None

    def validate_visible_delivery(self, response: dict[str, Any]) -> bool:
        msg_id = self.extract_message_id(response)
        if not msg_id:
            return False
        return bool(response.get("ok", True))
