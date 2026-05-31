# NEWSBOT V3 ARCHITECTURE

Изоляция v3 рядом с v2; единый MAX client; llm_router; official JSON первичный; fullarticle callback-only.

## Read-more policy (v3)

- Не каждая новость получает кнопку `📖 Читать полностью`.
- Для длинной новости (существенно длиннее short-post, и выше порогов `READ_MORE_MIN_FULL_TEXT_CHARS` / `READ_MORE_MIN_EXTRA_CHARS_OVER_POST`) добавляется **только внутренняя** callback-кнопка `full_article:<news_id>`.
- Кнопка `📖 Читать полностью` никогда не должна открывать внешний URL.
- Внешняя ссылка источника остаётся отдельной строкой в short-post и в атрибуции full article.
- Для коротких новостей кнопка не добавляется; показывается только source block.

## Step 4 seller output dry-run contract
- Seller post contract: **title**, short summary, `Вывод для селлера`, one importance indicator (🔴/🟡/🔵), source block.
- Source policy: when `item.link` exists, source URL must remain visible in post text.
- Read-more policy: only internal callback `full_article:<news_id>` and only for long news.
- External URL button for read-more is forbidden.

## Step 5 publisher dry-run + MAX mock
- Dry-run chain: source/migrated -> scoring/seller output -> post builder -> MAX mock send -> mock message_id -> send_attempt/published_message plan.
- MAX mock only: no real sends, deterministic mock message_id, external URL button forbidden.
- SendAttempt/PublishedMessage are planned objects only; no DB mark until confirmed send.
- Seller Helper CTA is separate second message; CTA failure does not rollback main post.
- Read-more is internal callback only: full_article:<id>.

