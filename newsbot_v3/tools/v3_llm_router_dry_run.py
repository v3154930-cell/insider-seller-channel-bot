#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _ensure_app_importable() -> None:
    this_file = Path(__file__).resolve()
    runtime_root = this_file.parent.parent
    if str(runtime_root) not in sys.path:
        sys.path.insert(0, str(runtime_root))


_ensure_app_importable()

from app.scoring.llm_router import LLMRouter  # noqa: E402


SAMPLE_TEXT = (
    "Маркетплейс обновил правила обработки возвратов для продавцов. "
    "Изменения вступают в силу после публикации в личном кабинете; "
    "продавцам рекомендуется проверить настройки склада и инструкции для сотрудников."
)


def _build_env(args: argparse.Namespace) -> dict:
    env = dict(os.environ)
    env["LLM_MODE"] = args.llm_mode
    env["LLM_PROVIDER"] = args.provider

    if args.timeout is not None:
        env["LLM_TIMEOUT_SECONDS"] = str(args.timeout)

    if args.github_model:
        env["GITHUB_MODELS_MODEL"] = args.github_model

    if args.gigachat_model:
        env["GIGACHAT_MODEL"] = args.gigachat_model

    return env


def _diagnostic_view(result: dict) -> dict:
    keys = [
        "llm_status",
        "llm_provider_used",
        "llm_attempt",
        "llm_fallback_used",
        "llm_error",
        "summary_mode",
        "llm_enabled",
        "llm_provider_primary",
        "prompt_type",
    ]
    return {key: result.get(key) for key in keys}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run LLMRouter without publishing, queue mutation, cron changes, "
            "live-send, or wrapper side effects."
        )
    )
    parser.add_argument(
        "--llm-mode",
        default="disabled",
        help=(
            "Router mode. Default is disabled and performs no external LLM calls. "
            "Use enabled/live/on/real only for explicit provider checks."
        ),
    )
    parser.add_argument(
        "--provider",
        default="github_models",
        help="Primary provider for enabled mode: github_models or gigachat.",
    )
    parser.add_argument(
        "--prompt-type",
        default="seller_summary",
        help="Prompt type from app.scoring.prompts.",
    )
    parser.add_argument(
        "--text",
        default=SAMPLE_TEXT,
        help="News text to route through the LLMRouter.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Optional LLM timeout in seconds for this dry-run process.",
    )
    parser.add_argument(
        "--github-model",
        default=None,
        help="Optional GitHub Models model override for this dry-run process.",
    )
    parser.add_argument(
        "--gigachat-model",
        default=None,
        help="Optional GigaChat model override for this dry-run process.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full router result as JSON.",
    )
    args = parser.parse_args()

    router = LLMRouter(env=_build_env(args))
    result = router.run(
        args.text,
        prompt_type=args.prompt_type,
        scoring={
            "importance_indicator": "🟡",
            "importance_reason": "dry_run",
            "actionability_score": 1,
            "is_low_value": False,
        },
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("V3_LLM_ROUTER_DRY_RUN_STATUS=OK")
        for key, value in _diagnostic_view(result).items():
            print(f"{key}={value}")
        print(f"summary={result.get('summary', '')}")
        print(f"seller_conclusion={result.get('seller_conclusion', '')}")
        print("production_mutation=false")
        print("queue_mutation=false")
        print("live_send=false")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
