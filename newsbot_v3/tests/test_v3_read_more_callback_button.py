from app.models import NewsItem
from app.publisher.post_builder import build_post


def _item(**overrides):
    base = NewsItem(
        news_id="90045",
        title="Заголовок",
        text="Короткий пост https://example.com/raw",
        link="https://example.com/source",
        source_name="TG:example https://example.com/source-name",
    )
    base.raw_text = "x" * 2000
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def test_regular_v3_long_post_uses_callback_read_more_button_only():
    post = build_post(_item())

    assert post["read_more_needed"] is True
    assert post["button_text"] == "Читать полностью"
    assert post["read_more_button_type"] == "callback"
    assert post["callback_payload"] == "full_article:90045"
    assert post["read_more_payload"] == "full_article:90045"
    assert post["callback_button_used"] is True
    assert post["source_url_button_used"] is False
    assert post["external_url_button_forbidden"] is True
    assert post["source_url_present"] is True
    assert post["raw_source_url_in_main_post"] is False
    assert post["source_link_preview_suppressed"] is True
    assert "Источник: TG:example" in post["text"]
    assert "http://" not in post["text"]
    assert "https://" not in post["text"]
    assert "Ссылка на источник:" not in post["text"]


def test_short_post_has_no_read_more_button_but_keeps_source_url_metadata_only():
    item = _item()
    item.raw_text = "x" * 50
    post = build_post(item)

    assert post["read_more_needed"] is False
    assert post["button_text"] is None
    assert post["callback_payload"] is None
    assert post["read_more_button_type"] == "none"
    assert post["source_link_present"] is True
    assert post["source_url_present"] is True
    assert post["source_url_button_used"] is False
    assert post["external_url_button_forbidden"] is True
    assert post["raw_source_url_in_main_post"] is False
    assert post["source_link_preview_suppressed"] is True
    assert "Источник:" in post["text"]
    assert "http://" not in post["text"]
    assert "https://" not in post["text"]
