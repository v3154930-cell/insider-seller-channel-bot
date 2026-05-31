from app.models import NewsItem
from app.publisher.post_builder import APPROVED_CATEGORY_LABELS, build_post


def _item(**overrides):
    item = NewsItem(
        news_id="sanitizer-1",
        title="🔴 Важно Заголовок 🟡",
        text="🟠 Обратите внимание\nКороткий пост 🟡",
        link="https://example.com/source",
        source_name="example.com",
    )
    for key, value in overrides.items():
        setattr(item, key, value)
    return item


def _approved_beacon_count(text: str) -> int:
    return sum(text.count(label) for label in APPROVED_CATEGORY_LABELS)


def test_regular_post_contains_exactly_one_approved_beacon_label():
    post = build_post(
        _item(),
        {
            "summary": "🔵 Интересно / аналитика\nСводка без маяка 🟡",
            "seller_conclusion": "🟢 Хорошая новость\nПрямых действий нет 🟡",
            "category_label": "🟠 Обратите внимание",
        },
    )

    assert post["category_label"] == "🟠 Обратите внимание"
    assert post["category_indicator"] == "🟠"
    assert _approved_beacon_count(post["text"]) == 1
    assert post["text"].count("🟠 Обратите внимание") == 1
    assert "🟡" not in post["text"]


def test_regular_post_maps_legacy_yellow_to_attention_label():
    item = _item(title="Заголовок", text="Короткий пост")
    post = build_post(item, {"importance_indicator": "🟡"})

    assert post["category_label"] == "🟠 Обратите внимание"
    assert post["category_indicator"] == "🟠"
    assert _approved_beacon_count(post["text"]) == 1
    assert "🟡" not in post["text"]
