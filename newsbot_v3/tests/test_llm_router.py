from __future__ import annotations

import json
from urllib import error

import pytest

from app.scoring.llm_router import LLMRouter


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def _chat_payload(content: str) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": content,
                }
            }
        ]
    }


def test_disabled_mode_uses_rules_without_external_calls(monkeypatch):
    def fail_urlopen(*args, **kwargs):
        raise AssertionError("disabled mode must not call external providers")

    monkeypatch.setattr("app.scoring.llm_router.request.urlopen", fail_urlopen)

    result = LLMRouter(env={"LLM_MODE": "disabled"}).run(
        "Текст новости для безопасного fallback.",
        scoring={"actionability_score": 0, "is_low_value": True},
    )

    assert result["llm_status"] == "disabled"
    assert result["llm_provider_used"] == "disabled"
    assert result["llm_attempt"] == 0
    assert result["llm_fallback_used"] is True
    assert result["llm_error"] == ""
    assert result["summary_mode"] == "rules"
    assert result["summary"] == "Текст новости для безопасного fallback."
    assert result["seller_conclusion"] == "Прямого действия для селлера не требуется; новость носит справочный характер."


def test_github_models_success_uses_primary_provider(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None, context=None):
        calls.append(req.full_url)
        return _FakeResponse(
            _chat_payload(
                json.dumps(
                    {
                        "summary": "Краткое резюме от GitHub Models.",
                        "seller_conclusion": "Проверьте настройки в кабинете продавца.",
                    },
                    ensure_ascii=False,
                )
            )
        )

    monkeypatch.setattr("app.scoring.llm_router.request.urlopen", fake_urlopen)

    result = LLMRouter(
        env={
            "LLM_MODE": "enabled",
            "LLM_PROVIDER": "github_models",
            "GITHUB_MODELS_TOKEN": "token",
        }
    ).run("Новость про изменение правил.")

    assert calls == ["https://models.github.ai/inference/chat/completions"]
    assert result["llm_status"] == "ok"
    assert result["llm_provider_used"] == "github_models"
    assert result["llm_attempt"] == 1
    assert result["llm_fallback_used"] is False
    assert result["llm_error"] == ""
    assert result["summary_mode"] == "llm"
    assert result["summary"] == "Краткое резюме от GitHub Models."
    assert result["seller_conclusion"] == "Проверьте настройки в кабинете продавца."


def test_primary_failure_falls_back_to_gigachat(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None, context=None):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise error.URLError("github unavailable")
        return _FakeResponse(
            _chat_payload(
                json.dumps(
                    {
                        "summary": "Резюме от GigaChat.",
                        "seller_conclusion": "Проверьте затронутые категории.",
                    },
                    ensure_ascii=False,
                )
            )
        )

    monkeypatch.setattr("app.scoring.llm_router.request.urlopen", fake_urlopen)

    result = LLMRouter(
        env={
            "LLM_MODE": "enabled",
            "LLM_PROVIDER": "github_models",
            "GITHUB_MODELS_TOKEN": "token",
            "GIGACHAT_ACCESS_TOKEN": "token",
        }
    ).run("Новость про сроки обновления API.")

    assert calls == [
        "https://models.github.ai/inference/chat/completions",
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
    ]
    assert result["llm_status"] == "ok"
    assert result["llm_provider_used"] == "gigachat"
    assert result["llm_attempt"] == 2
    assert result["llm_fallback_used"] is False
    assert "github_models:" in result["llm_error"]
    assert result["summary_mode"] == "llm"
    assert result["summary"] == "Резюме от GigaChat."
    assert result["seller_conclusion"] == "Проверьте затронутые категории."


def test_all_provider_failures_use_conservative_template_fallback(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None, context=None):
        calls.append(req.full_url)
        raise error.URLError("network unavailable")

    monkeypatch.setattr("app.scoring.llm_router.request.urlopen", fake_urlopen)

    result = LLMRouter(
        env={
            "LLM_MODE": "enabled",
            "LLM_PROVIDER": "github_models",
            "GITHUB_MODELS_TOKEN": "token",
            "GIGACHAT_ACCESS_TOKEN": "token",
        }
    ).run(
        "Официальное изменение комиссии для продавцов.",
        scoring={"actionability_score": 2, "is_low_value": False, "importance_indicator": "🔴"},
    )

    assert calls == [
        "https://models.github.ai/inference/chat/completions",
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
    ]
    assert result["llm_status"] == "error"
    assert result["llm_provider_used"] == "template"
    assert result["llm_attempt"] == 2
    assert result["llm_fallback_used"] is True
    assert "github_models:" in result["llm_error"]
    assert "gigachat:" in result["llm_error"]
    assert result["summary_mode"] == "fallback"
    assert result["summary"] == "Официальное изменение комиссии для продавцов."
    assert result["seller_conclusion"] == "Проверьте применимость изменения к вашему ассортименту и операционным процессам."
    assert result["importance_indicator"] == "🔴"


@pytest.mark.parametrize(
    ("mode", "expected_status", "expected_provider", "expected_attempt", "expected_summary_mode"),
    [
        ("primary_ok_mock", "ok", "github_models", 1, "llm"),
        ("primary_fail_fallback_ok_mock", "ok", "gigachat", 2, "llm"),
        ("all_fail_template_fallback_mock", "error", "template", 2, "fallback"),
    ],
)
def test_legacy_mock_modes_remain_available(
    mode,
    expected_status,
    expected_provider,
    expected_attempt,
    expected_summary_mode,
):
    result = LLMRouter(env={"LLM_MODE": mode, "LLM_PROVIDER": "github_models"}).run("Текст новости.")

    assert result["llm_status"] == expected_status
    assert result["llm_provider_used"] == expected_provider
    assert result["llm_attempt"] == expected_attempt
    assert result["summary_mode"] == expected_summary_mode
    assert "llm_error" in result
    assert result["summary"]


def test_unknown_enabled_mode_is_safe_and_skips_external_calls(monkeypatch):
    def fail_urlopen(*args, **kwargs):
        raise AssertionError("unknown mode must not call external providers")

    monkeypatch.setattr("app.scoring.llm_router.request.urlopen", fail_urlopen)

    result = LLMRouter(env={"LLM_MODE": "surprise"}).run("Новость.")

    assert result["llm_status"] == "fallback"
    assert result["llm_provider_used"] == "template"
    assert result["llm_attempt"] == 0
    assert result["llm_fallback_used"] is True
    assert result["summary_mode"] == "fallback"
    assert "Unsupported LLM_MODE" in result["llm_error"]
