from app.models import NewsItem
from app.publisher.post_builder import build_seller_reasoning


def _item(importance="🟡"):
    return NewsItem(
        news_id="reasoning-1",
        title="Заголовок",
        text="Текст",
        link="https://example.com/source",
        source_name="example.com",
        importance=importance,
    )


def test_seller_result_category_label_wins():
    reasoning = build_seller_reasoning(_item(importance="🔴"), {"category_label": "🟢 Хорошая новость"})

    assert reasoning == {
        "category_label": "🟢 Хорошая новость",
        "category_indicator": "🟢",
    }


def test_missing_category_label_falls_back_to_legacy_importance_mapping():
    for legacy in ("🟡", "🟠"):
        reasoning = build_seller_reasoning(_item(importance="🔵"), {"importance_indicator": legacy})

        assert reasoning == {
            "category_label": "🟠 Обратите внимание",
            "category_indicator": "🟠",
        }


def test_missing_seller_result_falls_back_to_item_importance():
    reasoning = build_seller_reasoning(_item(importance="🔵"), None)

    assert reasoning == {
        "category_label": "🔵 Интересно / аналитика",
        "category_indicator": "🔵",
    }
