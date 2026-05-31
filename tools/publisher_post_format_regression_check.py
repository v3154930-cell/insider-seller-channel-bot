#!/usr/bin/env python3
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stable_publisher_v3 import build_seller_post, build_read_more_button, safe_trim_post, _pick_image_url, build_seller_helper_cta_text


def assert_post_contract(item):
    post, trimmed = safe_trim_post(build_seller_post(item), 1200)
    assert re.search(r"<b>.+</b>", post), "bold title missing"
    assert "Вывод для селлера:" in post, "seller conclusion block missing"
    assert any(ind in post for ind in ["🔴 Важно для селлера", "🟡 Общая информация", "🔵 Просто интересно"]), "importance indicator missing"
    assert "Проверьте применимость новости к своим товарам" not in post
    assert "Пересчитайте влияние на маржу" not in post
    assert "Обновите операционный план" not in post
    assert len(post) <= 1200
    if item.get("link"):
        btn = build_read_more_button(item)
        assert bool(btn), "read-more button missing"
        assert btn.get("type") == "callback", "read-more must be callback button"
        assert str(btn.get("payload", "")).startswith("full_article:"), "read-more payload must be full_article callback"
        assert item["link"] not in post, "source link should be in button, not post body"
    return post, trimmed


def run_dry_run_diagnostics_with_empty_db():
    with NamedTemporaryFile(suffix=".db") as f:
        conn = sqlite3.connect(f.name)
        conn.execute(
            """
            CREATE TABLE news (
                id INTEGER PRIMARY KEY,
                title TEXT,
                raw_text TEXT,
                source TEXT,
                seller_analysis TEXT,
                processed_text TEXT,
                link TEXT,
                full_article_news_id INTEGER,
                seller_decision TEXT,
                seller_relevance_score REAL,
                actionability_score REAL,
                is_published INTEGER DEFAULT 0,
                max_message_id TEXT,
                full_article_published_at TEXT,
                created_at TEXT
            )
            """
        )
        conn.commit()
        conn.close()

        cmd = [sys.executable, str(Path(__file__).resolve().parents[1] / "stable_publisher_v3.py"), "--dry-run"]
        env = dict(__import__("os").environ)
        env["NEWS_DB_PATH"] = f.name
        out = subprocess.check_output(cmd, text=True, env=env)

    assert "selected_reason=none" in out
    assert "send_status=skipped_no_candidate" in out
    required_defaults = {
        "read_more_button_present=false",
        "read_more_url_present=false",
        "image_present=false",
        "image_attach_attempted=false",
        "importance_indicator=",
        "post_length=0",
        "post_was_trimmed=false",
    }
    for marker in required_defaults:
        assert marker in out, f"missing no-candidate default marker: {marker}"


def main():
    cases = [
        {"id": 101, "title": "WB обновил тарифы логистики", "processed_text": "Новые тарифы вступают в силу со следующей недели. Это изменит unit-экономику и потребует корректировки цен.", "source": "VC", "link": "https://example.com/wb", "image_url": "https://example.com/img.jpg"},
        {"id": 102, "title": "Рынок ecom вырос на 12%", "processed_text": "Исследование показало рост и изменение структуры спроса.", "source": "Retail", "link": "https://example.com/market"},
        {"title": "Бренд запустил новую кампанию", "processed_text": "Новость без прямого операционного действия для селлеров.", "source": "News"},
    ]

    helper_text = build_seller_helper_cta_text()
    assert helper_text and "Проверить комиссию" in helper_text

    for case in cases:
        assert_post_contract(case)
        if _pick_image_url(case):
            assert _pick_image_url(case).startswith("http")

    run_dry_run_diagnostics_with_empty_db()
    print("OK")


if __name__ == "__main__":
    main()
