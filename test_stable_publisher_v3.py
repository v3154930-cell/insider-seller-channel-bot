import os

from stable_publisher_v3 import (
    build_buttons_for_item,
    build_max_payload_preview,
    build_post,
    get_helper_button_url,
)


def test_dedupe_no_broken_word_fragment():
    item = {
        "id": 69381,
        "title": "Онлайн-покупке. Для половины пользователей маркетплейсов важна быстрая доставка.",
        "processed_text": "Онлайн-покупке. Для половины пользователей маркетплейсов важна быстрая доставка. Остальные ценят цену.",
        "source": "src",
        "link": "https://example.com",
    }
    post = build_post(item)
    body = post.split("\n\n", 1)[1]
    assert not body.startswith("айн-покупке")
    first_body_line = body.splitlines()[0]
    assert first_body_line
    assert not first_body_line[0].islower()


def test_dry_run_none_still_prints_diagnostics():
    # Contract test for formatting helpers used in dry-run diagnostics.
    buttons = build_buttons_for_item({"id": 1}, "")
    payload = build_max_payload_preview("text", buttons)
    assert buttons[0][0]["payload"] == "full_article:1"
    assert "attachments" in payload


def test_helper_url_missing_reports_false(monkeypatch):
    for k in ("SELLER_HELPER_BOT_URL", "HELPER_BOT_URL", "SELLER_HELPER_URL", "SELLER_HELPER_BOT_LINK"):
        monkeypatch.delenv(k, raising=False)
    assert get_helper_button_url() == ""
    buttons = build_buttons_for_item({"id": 7}, "")
    assert len(buttons) == 1


def test_helper_url_present_adds_button(monkeypatch):
    monkeypatch.setenv("SELLER_HELPER_BOT_URL", "https://max.ru/seller_helper")
    helper_url = get_helper_button_url()
    assert helper_url == "https://max.ru/seller_helper"
    buttons = build_buttons_for_item({"id": 7}, helper_url)
    assert len(buttons) == 2
    assert buttons[1][0]["type"] == "link"
    assert buttons[1][0]["url"] == "https://max.ru/seller_helper"
