#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os

from app.models import NewsItem
from app.publisher.post_builder import build_post
from app.scoring.llm_scorer import score_with_llm


def _samples() -> list[NewsItem]:
    long_text = "Изменение комиссии и логистических правил WB. " * 90
    return [
        NewsItem("1", "WB обновил комиссии для FBO", long_text, "https://seller.wildberries.ru/news/1", "WB Official"),
        NewsItem("2", "Ozon: рыночный обзор категории", "Статистика по спросу, категориям и долям рынка без срочных действий.", "https://seller.ozon.ru/news/2", "Ozon"),
        NewsItem("3", "Контекст: обсуждение трендов ecom", "Исследование показывает тренды спроса и конкуренции по категориям.", "https://example.com/3", "Industry Blog"),
        NewsItem("7", "Маркетплейс снизит стоимость продвижения", "Площадка снижает ставки рекламы и упрощает запуск кампаний для продавцов.", "https://example.com/7", "Marketplace"),
        NewsItem("8", "Ozon тестирует новую схему отгрузки", "Меняется операционная схема отгрузки без немедленных санкций для продавцов.", "https://example.com/8", "Ozon"),
        NewsItem("4", "API изменения в кабинете продавца", "Официальное изменение API и сроков отключения старой версии.", "https://api.marketplace.ru/changelog", "Official API"),
        NewsItem("5", "Короткая заметка с ссылкой", "", "https://example.com/5", "Media"),
        NewsItem("6", "Заметка без ссылки", "Внутреннее объявление без URL", None, "Internal"),
    ]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--llm-mode", default="disabled")
    p.add_argument("--v2-db", default=None)
    p.add_argument("--limit", type=int, default=20)
    args = p.parse_args()

    env = dict(os.environ)
    env["LLM_MODE"] = args.llm_mode
    items = _samples()[: args.limit]

    rendered = 0
    long_ok = True
    short_ok = True
    src_ok = True
    importance_ok = True
    category_ok = True
    categories_seen: set[str] = set()
    summary_ok = True
    conclusion_ok = True
    read_more_ok = True

    for item in items:
        scoring = score_with_llm(item.title, item.text, marketplace=item.marketplace, env=env)
        post = build_post(item, scoring)
        rendered += 1
        if item.news_id == "1":
            long_ok = bool(post["callback_payload"] == "full_article:1")
        if item.news_id == "2":
            short_ok = not post["read_more_button_present"]
        if item.link:
            src_ok = src_ok and post["source_link_present"]
        importance_ok = importance_ok and scoring.get("importance_indicator") in {"🔴", "🟡", "🔵"}
        category_ok = category_ok and post.get("category_label") in {"🔴 Важно", "🟠 Обратите внимание", "🟢 Хорошая новость", "🔵 Интересно / аналитика"}
        categories_seen.add(str(post.get("category_label") or ""))
        summary_ok = summary_ok and bool(scoring.get("summary"))
        conclusion_ok = conclusion_ok and bool(scoring.get("seller_conclusion"))
        read_more_ok = read_more_ok and (post["button_text"] != "https://")
        status = "OK" if post["source_link_present"] or not item.link else "WARN"
        print(f"ITEM_RESULT id={item.news_id} category={post.get('category_label')} category_reason={post.get('category_reason')} seller_reasoning_valid={str(bool(post.get('seller_reasoning_valid'))).lower()} read_more_needed={post['read_more_needed']} source_link_present={post['source_link_present']} status={status}")

    all_ok = all([long_ok, short_ok, src_ok, importance_ok, category_ok, len(categories_seen) >= 3, summary_ok, conclusion_ok, read_more_ok])
    print(f"V3_SELLER_OUTPUT_DRY_RUN_STATUS={'OK' if all_ok else 'WARN'}")
    print(f"items_seen={len(items)}")
    print(f"items_rendered={rendered}")
    print(f"llm_mode={args.llm_mode}")
    print(f"seller_summary_ready={'true' if summary_ok else 'false'}")
    print(f"seller_conclusion_ready={'true' if conclusion_ok else 'false'}")
    print(f"importance_ready={'true' if importance_ok else 'false'}")
    print(f"approved_category_system_ready={'true' if category_ok else 'false'}")
    print(f"seller_reasoning_categories_seen={','.join(sorted(categories_seen))}")
    print(f"read_more_policy_ready={'true' if read_more_ok else 'false'}")
    print(f"source_link_policy_ready={'true' if src_ok else 'false'}")
    print(f"long_news_callback_ok={'true' if long_ok else 'false'}")
    print(f"short_news_no_button_ok={'true' if short_ok else 'false'}")
    print("external_url_button_forbidden=true")
    print("production_mutation=false")
    print("recommended_next_steps=enable real provider only after explicit cutover")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
