# LLM Failover

Primary github/openai-compatible -> GigaChat fallback -> conservative template fallback; no secrets in logs; collector independent from LLM.

## Step 4 behavior
- All LLM interactions go via `app/scoring/llm_router.py`.
- Default mode is dry-run mock (`disabled`), no network calls.
- On provider fail, fallback to mock fallback provider; if all fail, conservative template fallback.
- Diagnostics required: `llm_enabled`, `llm_provider_primary`, `llm_provider_used`, `llm_attempt`, `llm_status`, `llm_fallback_used`, `prompt_type`.
