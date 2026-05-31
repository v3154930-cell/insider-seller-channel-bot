from __future__ import annotations

from .llm_router import LLMRouter
from .seller_relevance import evaluate_seller_relevance
from app.publisher.seller_reasoning import build_seller_reasoning


def score_with_llm(title: str, text: str, marketplace: str | None = None, env: dict | None = None, source: str | None = None) -> dict:
    scoring = evaluate_seller_relevance(title, text, marketplace, source=source)
    router = LLMRouter(env=env)

    summary = router.run(text, prompt_type="seller_summary", scoring=scoring)
    conclusion = router.run(text, prompt_type="seller_conclusion", scoring=scoring)

    out = {**scoring}
    out.update(
        {
            "summary": summary.get("summary", ""),
            "seller_conclusion": conclusion.get("seller_conclusion", ""),
            "summary_mode": "llm" if summary.get("llm_status") == "ok" else ("fallback" if summary.get("llm_status") in {"fallback", "error"} else "rules"),
            "llm_diagnostics": summary,
        }
    )
    reasoning = build_seller_reasoning(
        title=title,
        text=text,
        tags=out.get("topics", []),
        scores=out,
        direct_action_status="none" if out.get("no_direct_action") else "direct_action",
        llm_output={"seller_conclusion": out.get("seller_conclusion", "")},
    )
    out.update(reasoning)
    out["seller_conclusion"] = reasoning["seller_conclusion"]
    return out
