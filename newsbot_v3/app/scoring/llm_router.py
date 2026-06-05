from __future__ import annotations

import json
import os
import ssl
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from .fallback_rules import conservative_fallback
from .prompts import get_prompt

try:
    from app.editor.editor_profile import EDITOR_PROFILE_V1
except Exception:
    EDITOR_PROFILE_V1 = ""


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    content: str


class LLMRouter:
    """Three-contour LLM router.

    Contours:
    1. GitHub Models, OpenAI-compatible chat completions.
    2. GigaChat API, OpenAI-like chat completions.
    3. Conservative rules/template fallback.

    Safety invariant:
    LLM_MODE=disabled is the default and never performs external calls.
    """

    DEFAULT_PROVIDER = "github_models"
    FALLBACK_PROVIDER = "gigachat"
    TEMPLATE_PROVIDER = "template"

    REAL_MODES = {"enabled", "live", "on", "real"}
    MOCK_MODES = {
        "primary_ok_mock",
        "primary_fail_fallback_ok_mock",
        "all_fail_template_fallback_mock",
    }

    def __init__(self, env: dict | None = None):
        self.env = env or os.environ

    def run(self, text: str, prompt_type: str = "seller_summary", scoring: dict | None = None) -> dict:
        mode = self.env.get("LLM_MODE", "disabled").strip().lower()
        primary = self.env.get("LLM_PROVIDER", self.DEFAULT_PROVIDER).strip() or self.DEFAULT_PROVIDER
        enabled = mode != "disabled"
        prompt = get_prompt(prompt_type)
        if EDITOR_PROFILE_V1:
            prompt = f"{EDITOR_PROFILE_V1}\n\nБазовая инструкция задачи:\n{prompt}"

        base = {
            "llm_enabled": enabled,
            "llm_provider_primary": primary,
            "prompt_type": prompt_type,
        }

        if not enabled:
            return self._with_diagnostics(
                base=base,
                payload=conservative_fallback(text, scoring),
                provider_used="disabled",
                attempt=0,
                status="disabled",
                fallback_used=True,
                error="",
                summary_mode="rules",
            )

        if mode in self.MOCK_MODES:
            return self._run_mock_mode(
                mode=mode,
                base=base,
                text=text,
                primary=primary,
                scoring=scoring,
            )

        if mode not in self.REAL_MODES:
            return self._with_diagnostics(
                base=base,
                payload=conservative_fallback(text, scoring),
                provider_used=self.TEMPLATE_PROVIDER,
                attempt=0,
                status="fallback",
                fallback_used=True,
                error=f"Unsupported LLM_MODE={mode!r}; external LLM calls skipped.",
                summary_mode="fallback",
            )

        errors: list[str] = []
        provider_order = self._provider_order(primary)

        for attempt, provider in enumerate(provider_order, start=1):
            try:
                response = self._call_provider(provider, prompt=prompt, prompt_type=prompt_type, text=text)
                payload = self._payload_from_llm_content(
                    content=response.content,
                    prompt_type=prompt_type,
                    text=text,
                    scoring=scoring,
                )
                return self._with_diagnostics(
                    base=base,
                    payload=payload,
                    provider_used=response.provider,
                    attempt=attempt,
                    status="ok",
                    fallback_used=False,
                    error="; ".join(errors) if errors else "",
                    summary_mode="llm",
                )
            except Exception as exc:
                errors.append(f"{provider}: {exc}")

        return self._with_diagnostics(
            base=base,
            payload=conservative_fallback(text, scoring),
            provider_used=self.TEMPLATE_PROVIDER,
            attempt=len(provider_order),
            status="error",
            fallback_used=True,
            error="; ".join(errors),
            summary_mode="fallback",
        )

    def _provider_order(self, primary: str) -> list[str]:
        order: list[str] = []
        for provider in (primary, self.FALLBACK_PROVIDER):
            if provider and provider not in order:
                order.append(provider)
        return order

    def _run_mock_mode(self, mode: str, base: dict, text: str, primary: str, scoring: dict | None) -> dict:
        fallback = conservative_fallback(text, scoring)

        if mode == "primary_ok_mock":
            return self._with_diagnostics(
                base=base,
                payload={
                    **fallback,
                    "summary": (text[:240] or fallback["summary"]),
                    "seller_conclusion": "Проверьте применимость для вашего магазина только если изменение затрагивает ваши процессы.",
                },
                provider_used=primary,
                attempt=1,
                status="ok",
                fallback_used=False,
                error="",
                summary_mode="llm",
            )

        if mode == "primary_fail_fallback_ok_mock":
            return self._with_diagnostics(
                base=base,
                payload={
                    **fallback,
                    "summary": (text[:220] or fallback["summary"]),
                    "seller_conclusion": "Приоритизируйте проверку только для затронутых категорий и операций.",
                },
                provider_used=self.FALLBACK_PROVIDER,
                attempt=2,
                status="ok",
                fallback_used=True,
                error=f"{primary}: mock primary failure",
                summary_mode="llm",
            )

        return self._with_diagnostics(
            base=base,
            payload=fallback,
            provider_used=self.TEMPLATE_PROVIDER,
            attempt=2,
            status="error",
            fallback_used=True,
            error=f"{primary}: mock primary failure; {self.FALLBACK_PROVIDER}: mock fallback failure",
            summary_mode="fallback",
        )

    def _with_diagnostics(
        self,
        *,
        base: dict,
        payload: dict,
        provider_used: str,
        attempt: int,
        status: str,
        fallback_used: bool,
        error: str,
        summary_mode: str,
    ) -> dict:
        return {
            **base,
            **payload,
            "llm_status": status,
            "llm_provider_used": provider_used,
            "llm_attempt": attempt,
            "llm_fallback_used": fallback_used,
            "llm_error": error,
            "summary_mode": summary_mode,
        }

    def _call_provider(self, provider: str, *, prompt: str, prompt_type: str, text: str) -> ProviderResponse:
        normalized = provider.strip().lower()

        if normalized in {"github", "github_models", "github-models"}:
            return self._call_github_models(prompt=prompt, prompt_type=prompt_type, text=text)

        if normalized in {"gigachat", "giga_chat", "sber_gigachat"}:
            return self._call_gigachat(prompt=prompt, prompt_type=prompt_type, text=text)

        raise RuntimeError(f"unknown provider {provider!r}")

    def _call_github_models(self, *, prompt: str, prompt_type: str, text: str) -> ProviderResponse:
        token = self.env.get("GITHUB_MODELS_TOKEN") or self.env.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_MODELS_TOKEN or GITHUB_TOKEN is not configured")

        endpoint = self.env.get("GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference/chat/completions")
        model = self.env.get("GITHUB_MODELS_MODEL", "openai/gpt-4o-mini")
        body = self._chat_completion_body(model=model, prompt=prompt, prompt_type=prompt_type, text=text)

        data = self._post_json(
            endpoint,
            body=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=self._timeout(),
        )
        return ProviderResponse(provider="github_models", content=self._extract_chat_content(data))

    def _call_gigachat(self, *, prompt: str, prompt_type: str, text: str) -> ProviderResponse:
        access_token = self.env.get("GIGACHAT_ACCESS_TOKEN") or self.env.get("GIGACHAT_TOKEN")
        if not access_token:
            access_token = self._request_gigachat_access_token()

        endpoint = self.env.get("GIGACHAT_ENDPOINT", "https://gigachat.devices.sberbank.ru/api/v1/chat/completions")
        model = self.env.get("GIGACHAT_MODEL", "GigaChat")
        body = self._chat_completion_body(model=model, prompt=prompt, prompt_type=prompt_type, text=text)

        data = self._post_json(
            endpoint,
            body=body,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=self._timeout(),
            insecure_tls=self._gigachat_insecure_tls(),
        )
        return ProviderResponse(provider="gigachat", content=self._extract_chat_content(data))

    def _request_gigachat_access_token(self) -> str:
        auth_key = self.env.get("GIGACHAT_AUTH_KEY")
        if not auth_key:
            raise RuntimeError("GIGACHAT_ACCESS_TOKEN/GIGACHAT_TOKEN or GIGACHAT_AUTH_KEY is not configured")

        endpoint = self.env.get("GIGACHAT_OAUTH_ENDPOINT", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth")
        scope = self.env.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        payload = f"scope={scope}".encode("utf-8")

        data = self._post_raw(
            endpoint,
            body=payload,
            headers={
                "Authorization": f"Basic {auth_key}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
            },
            timeout=self._timeout(),
            insecure_tls=self._gigachat_insecure_tls(),
        )

        token = data.get("access_token")
        if not token:
            raise RuntimeError("GigaChat OAuth response does not contain access_token")
        return str(token)

    def _chat_completion_body(self, *, model: str, prompt: str, prompt_type: str, text: str) -> dict:
        safe_text = (text or "").strip()
        max_chars = int(self.env.get("LLM_INPUT_MAX_CHARS", "6000"))
        if max_chars > 0:
            safe_text = safe_text[:max_chars]

        return {
            "model": model,
            "temperature": float(self.env.get("LLM_TEMPERATURE", "0.1")),
            "max_tokens": int(self.env.get("LLM_MAX_TOKENS", "600")),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты редактор новостей для marketplace-селлеров. "
                        "Отвечай строго JSON-объектом с ключами summary и seller_conclusion. "
                        "Не добавляй Markdown, рекламу, выдуманные факты или советы вне текста новости."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Тип задачи: {prompt_type}\n"
                        f"Инструкция: {prompt}\n\n"
                        f"Текст новости:\n{safe_text}"
                    ),
                },
            ],
        }

    def _payload_from_llm_content(
        self,
        *,
        content: str,
        prompt_type: str,
        text: str,
        scoring: dict | None,
    ) -> dict:
        fallback = conservative_fallback(text, scoring)
        parsed = self._parse_llm_json(content)

        title_suggestion = self._clean_text(parsed.get("title_suggestion")) if isinstance(parsed, dict) else ""
        summary = self._clean_text(parsed.get("summary")) if isinstance(parsed, dict) else ""
        conclusion = self._clean_text(parsed.get("seller_conclusion")) if isinstance(parsed, dict) else ""

        if not summary and prompt_type in {"seller_summary", "digest_summary"}:
            summary = self._clean_text(content)

        if not conclusion and prompt_type == "seller_conclusion":
            conclusion = self._clean_text(content)

        return {
            **fallback,
            "title_suggestion": title_suggestion,
            "summary": summary or fallback["summary"],
            "seller_conclusion": conclusion or fallback["seller_conclusion"],
        }

    def _parse_llm_json(self, content: str) -> dict[str, Any]:
        stripped = (content or "").strip()
        if not stripped:
            return {}

        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "`` `".replace(" ", ""):
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()

        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            return {}

        return value if isinstance(value, dict) else {}

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).strip().split())

    def _extract_chat_content(self, data: dict) -> str:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("chat completion response does not contain choices")

        first = choices[0]
        if not isinstance(first, dict):
            raise RuntimeError("chat completion choice is not an object")

        message = first.get("message")
        if isinstance(message, dict) and message.get("content"):
            return str(message["content"])

        if first.get("text"):
            return str(first["text"])

        raise RuntimeError("chat completion response does not contain message content")

    def _post_json(
        self,
        url: str,
        *,
        body: dict,
        headers: dict[str, str],
        timeout: float,
        insecure_tls: bool = False,
    ) -> dict:
        return self._post_raw(
            url,
            body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            timeout=timeout,
            insecure_tls=insecure_tls,
        )

    def _post_raw(
        self,
        url: str,
        *,
        body: bytes,
        headers: dict[str, str],
        timeout: float,
        insecure_tls: bool = False,
    ) -> dict:
        req = request.Request(url, data=body, headers=headers, method="POST")
        context = ssl._create_unverified_context() if insecure_tls else None

        try:
            with request.urlopen(req, timeout=timeout, context=context) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"HTTP {exc.code}: {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(str(exc.reason)) from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("provider returned non-JSON response") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("provider returned non-object JSON response")

        return parsed

    def _timeout(self) -> float:
        return float(self.env.get("LLM_TIMEOUT_SECONDS", "20"))

    def _gigachat_insecure_tls(self) -> bool:
        return self.env.get("GIGACHAT_INSECURE_TLS", "0").strip().lower() in {"1", "true", "yes"}
