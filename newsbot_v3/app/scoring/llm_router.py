import os

from .fallback_rules import conservative_fallback
from .prompts import get_prompt


class LLMRouter:
    def __init__(self, env: dict | None = None):
        self.env = env or os.environ

    def run(self, text: str, prompt_type: str = "seller_summary", scoring: dict | None = None) -> dict:
        mode = self.env.get("LLM_MODE", "disabled")
        primary = self.env.get("LLM_PROVIDER", "github_models")
        enabled = mode != "disabled"
        _ = get_prompt(prompt_type)

        base = {
            "llm_enabled": enabled,
            "llm_provider_primary": primary,
            "prompt_type": prompt_type,
        }

        if not enabled:
            return {**base, "llm_provider_used": "disabled", "llm_attempt": 0, "llm_status": "disabled", "llm_fallback_used": True, **conservative_fallback(text, scoring)}

        if mode == "primary_ok_mock":
            fallback = conservative_fallback(text, scoring)
            return {**base, "llm_provider_used": primary, "llm_attempt": 1, "llm_status": "ok", "llm_fallback_used": False, "summary": (text[:700] or fallback["summary"]), "seller_conclusion": "Проверьте применимость для вашего магазина только если изменение затрагивает ваши процессы."}
        if mode == "primary_fail_fallback_ok_mock":
            fallback = conservative_fallback(text, scoring)
            return {**base, "llm_provider_used": "gigachat", "llm_attempt": 2, "llm_status": "fallback", "llm_fallback_used": True, "summary": (text[:700] or fallback["summary"]), "seller_conclusion": "Приоритизируйте проверку только для затронутых категорий и операций."}
        if mode == "all_fail_template_fallback_mock":
            return {**base, "llm_provider_used": "template", "llm_attempt": 2, "llm_status": "error", "llm_fallback_used": True, **conservative_fallback(text, scoring)}

        return {**base, "llm_provider_used": "template", "llm_attempt": 1, "llm_status": "fallback", "llm_fallback_used": True, **conservative_fallback(text, scoring)}
