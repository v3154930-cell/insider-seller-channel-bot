import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "build_analytics_periodic_draft_v1.py"
spec = importlib.util.spec_from_file_location("analytics_draft", MODULE_PATH)
analytics_draft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analytics_draft)


def row(**overrides):
    base = {
        "id": 1,
        "title": "Wildberries меняет тарифы для продавцов",
        "raw_text": "",
        "processed_text": "",
        "source": "tg channel",
        "source_type": "media",
        "reason_tags": "commission_tariff",
        "topic_tags": "",
        "seller_relevance_score": 20,
        "actionability_score": 10,
        "score": 5,
        "created_at": "2026-06-06 12:00:00",
    }
    base.update(overrides)
    return base


def test_promo_detection_from_phrases_and_reason_tags():
    assert analytics_draft.is_promotional_row(row(title="Осталось 2 часа до повышения тарифов, у меня есть телеграм-бот"))
    assert analytics_draft.is_promotional_row(row(reason_tags="native_ad, commission_tariff"))
    assert not analytics_draft.is_promotional_row(row(title="Ozon официально обновил правила оферты", source="OFFICIAL: ozon"))


def test_technical_tags_are_hidden_and_tags_are_normalized():
    assert analytics_draft.normalize_tag("seller_filter_live") is None
    assert analytics_draft.normalize_tag("tariff:levels=high:group_key=wb") is None
    assert analytics_draft.normalize_tag("commission_tariff") == "tariffs/commissions"
    assert analytics_draft.normalize_tag("logistics_storage") == "logistics/storage"


def test_marketplace_detection():
    assert analytics_draft.detect_marketplace(row(title="Wildberries обновил хранение")) == "wildberries"
    assert analytics_draft.detect_marketplace(row(title="Ozon обновил API")) == "ozon"
    assert analytics_draft.detect_marketplace(row(title="Новое требование для селлеров")) == "unknown"


def test_scoring_orders_official_above_promo():
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=7)
    official = row(id=1, title="OFFICIAL Ozon: изменены комиссии", source="OFFICIAL: ozon", source_type="official", seller_relevance_score=10)
    promo = row(id=2, title="Успейте записаться на курс про комиссии", reason_tags="promo", seller_relevance_score=60, actionability_score=60, score=60)
    assert analytics_draft.score(official, start, end) > analytics_draft.score(promo, start, end)
    top = analytics_draft.build_report([official, promo], 7, "all", None, start, end, limit_top=5)
    assert "Filtered promo/native/leadgen rows from top ranking: 1" in top["summary"]
    assert top["source_news_ids"] == "[1]"
