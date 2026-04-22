"""Unit tests for evaluate_item_relevance function in staging preview."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from staging.preview_staging import (
        evaluate_item_relevance,
        DOMAIN_BLACKLIST,
        extract_domain,
        get_item_url_local
    )
except ImportError:
    from preview_staging import (
        evaluate_item_relevance,
        DOMAIN_BLACKLIST,
        extract_domain,
        get_item_url_local
    )


@pytest.fixture
def sample_item_with_url():
    return {
        "id": 1,
        "title": "Ozon повысил комиссию на категорию",
        "description": "Маркетплейс Ozon объявил о повышении комиссии",
        "raw_text": "Ozon повысил комиссию на категорию электроника с 15% до 20%. Это коснется всех селлеров, работающих по модели FBS.",
        "url": "https://www.ozon.ru/info/commission-change/",
        "source": "Ozon News",
        "category": "general"
    }


@pytest.fixture
def item_no_url():
    return {
        "id": 2,
        "title": "Новость без ссылки",
        "description": "Какое-то важное событие",
        "raw_text": "Произошло важное событие для селлеров маркетплейсов",
        "url": "",
        "source": "Test Source",
        "category": "general"
    }


@pytest.fixture
def item_short_text():
    return {
        "id": 3,
        "title": "Короткий заголовок",
        "description": "Короткое",
        "raw_text": "Короткий текст",
        "url": "https://example.com",
        "source": "Test",
        "category": "general"
    }


@pytest.fixture
def item_no_marketplace_context():
    return {
        "id": 4,
        "title": "Погода в Москве солнечная",
        "description": "Сегодня в Москве тепло и солнечно",
        "raw_text": "Погода отличная, все хорошо",
        "url": "https://weather.ru/moscow",
        "source": "Weather",
        "category": "general"
    }


@pytest.fixture
def item_no_impact():
    return {
        "id": 5,
        "title": "Ozon открыл новый офис",
        "description": "Компания Ozon открыла офис в новом городе",
        "raw_text": "Ozon открыл новый офис в Казани. Это большое событие для компании.",
        "url": "https://ozon.ru/office",
        "source": "Ozon",
        "category": "general"
    }


@pytest.fixture
def item_blacklist_domain():
    return {
        "id": 6,
        "title": "Важная новость на VC.ru",
        "description": "Статья о маркетплейсах",
        "raw_text": "Это важная статья о том, как продавать на маркетплейсах",
        "url": "https://vc.ru/marketplace-news",
        "source": "VC.ru",
        "category": "general"
    }


@pytest.fixture
def item_stop_signal():
    return {
        "id": 7,
        "title": "Поздравляем победителей рейтинга селлеров",
        "description": "Опубликован ежегодный рейтинг лучших селлеров",
        "raw_text": "Поздравляем победителей рейтинга! Это большое событие для сообщества.",
        "url": "https://marketplace-awards.ru/winners",
        "source": "Awards",
        "category": "general"
    }


@pytest.fixture
def item_strong_relevance():
    return {
        "id": 8,
        "title": "Wildberries изменил условия оферты для селлеров",
        "description": "Маркетплейс Wildberries обновил оферту и повысил комиссию на 3%",
        "raw_text": "Wildberries объявил об изменении условий оферты. Комиссия на категорию одежда повышается с 12% до 15%. Изменения вступают в силу с 1 мая. Селлерам необходимо ознакомиться с новыми условиями доставки и хранения на складе.",
        "url": "https://wildberries.ru/services/seller-offer",
        "source": "WB News",
        "category": "general"
    }


@pytest.fixture
def item_interview():
    return {
        "id": 9,
        "title": "Интервью с главой Ozon",
        "description": "Глава Ozon рассказал о планах развития",
        "raw_text": "Интервью с генеральным директором Ozon о будущем компании",
        "url": "https://example.com/interview",
        "source": "Interview",
        "category": "general"
    }


class TestEvaluateItemRelevance:
    """Tests for evaluate_item_relevance gate function."""

    def test_reject_no_url(self):
        fixtures = get_test_fixtures()
        result = evaluate_item_relevance(fixtures["item_no_url"])
        assert result["passed"] is False
        assert any("нет ссылки" in r for r in result["reasons"])

    def test_reject_short_text(self):
        fixtures = get_test_fixtures()
        result = evaluate_item_relevance(fixtures["item_short_text"])
        assert result["passed"] is False
        assert any("короткий" in r.lower() for r in result["reasons"])

    def test_reject_no_marketplace_context(self):
        fixtures = get_test_fixtures()
        result = evaluate_item_relevance(fixtures["item_no_marketplace_context"])
        assert result["passed"] is False
        reasons_str = str(result["reasons"])
        assert "marketplace" in reasons_str.lower() or "маркетплейс" in reasons_str or "ozon" in reasons_str.lower()

    def test_reject_no_practical_impact(self):
        fixtures = get_test_fixtures()
        result = evaluate_item_relevance(fixtures["item_no_impact"])
        assert result["passed"] is False
        reasons_str = str(result["reasons"])
        assert "impact" in reasons_str.lower() or "влияние" in reasons_str or "практик" in reasons_str.lower()

    def test_reject_blacklist_domain(self):
        fixtures = get_test_fixtures()
        result = evaluate_item_relevance(fixtures["item_blacklist_domain"])
        assert result["passed"] is False
        assert any("черном списке" in r.lower() for r in result["reasons"])

    def test_reject_stop_signal_congratulations(self):
        fixtures = get_test_fixtures()
        result = evaluate_item_relevance(fixtures["item_stop_signal"])
        assert result["passed"] is False
        reasons_str = str(result["reasons"])
        assert "stop" in reasons_str.lower() or "рейтинг" in reasons_str or "congratulations" in reasons_str.lower()

    def test_reject_interview(self):
        fixtures = get_test_fixtures()
        result = evaluate_item_relevance(fixtures["item_interview"])
        assert result["passed"] is False
        assert "интервью" in str(result["reasons"]).lower()

    def test_pass_strong_relevance(self):
        fixtures = get_test_fixtures()
        result = evaluate_item_relevance(fixtures["item_strong_relevance"])
        assert result["passed"] is True
        assert result["score"] >= 60

    def test_pass_has_url(self):
        """URL alone is NOT sufficient for pass - need URL + context + impact + score >= 60."""
        fixtures = get_test_fixtures()
        result = evaluate_item_relevance(fixtures["sample_item_with_url"])
        assert result["passed"] is True, f"URL + MP context + impact should pass with score >= 60, got score={result['score']}: {result['reasons']}"
        assert result["score"] >= 60, f"Expected score >= 60, got {result['score']}"

    def test_extract_domain(self):
        """Test domain extraction from URL."""
        assert extract_domain("https://vc.ru/news") == "vc.ru"
        assert extract_domain("https://www.ozon.ru/info/") == "ozon.ru"
        assert extract_domain("http://example.com/path") == "example.com"
        assert extract_domain("") == ""
        assert extract_domain("not-a-url") == ""

    def test_blacklist_includes_vc_ru(self):
        """Verify vc.ru is in blacklist."""
        assert "vc.ru" in DOMAIN_BLACKLIST

    def test_blacklist_includes_rbc_ru(self):
        """Verify rbc.ru is in blacklist per policy."""
        assert "rbc.ru" in DOMAIN_BLACKLIST


def get_test_fixtures():
    """Define test fixtures inline to avoid conftest dependency issues."""
    
    sample_item_with_url = {
        "id": 1,
        "title": "Ozon повысил комиссию на категорию",
        "description": "Маркетплейс Ozon объявил о повышении комиссии",
        "raw_text": "Ozon повысил комиссию на категорию электроника с 15% до 20%. Это коснется всех селлеров, работающих по модели FBS.",
        "url": "https://www.ozon.ru/info/commission-change/",
        "source": "Ozon News",
        "category": "general"
    }
    
    item_no_url = {
        "id": 2,
        "title": "Новость без ссылки",
        "description": "Какое-то важное событие",
        "raw_text": "Произошло важное событие для селлеров маркетплейсов",
        "url": "",
        "source": "Test Source",
        "category": "general"
    }
    
    item_short_text = {
        "id": 3,
        "title": "Короткий заголовок",
        "description": "Короткое",
        "raw_text": "Короткий текст",
        "url": "https://example.com",
        "source": "Test",
        "category": "general"
    }
    
    item_no_marketplace_context = {
        "id": 4,
        "title": "Погода в Москве солнечная",
        "description": "Сегодня в Москве тепло и солнечно",
        "raw_text": "Погода отличная, все хорошо. О погоде в Москве можно узнать на сайте weather.ru. Сегодня тепло, завтра тоже будет тепло.",
        "url": "https://weather.ru/moscow",
        "source": "Weather",
        "category": "general"
    }
    
    item_no_impact = {
        "id": 5,
        "title": "Ozon открыл новый офис",
        "description": "Компания Ozon открыла офис в новом городе",
        "raw_text": "Ozon открыл новый офис в Казани. Это большое событие для компании. Офис находится в центре города и будет открыт для сотрудников и гостей.",
        "url": "https://ozon.ru/office",
        "source": "Ozon",
        "category": "general"
    }
    
    item_blacklist_domain = {
        "id": 6,
        "title": "Важная новость на VC.ru",
        "description": "Статья о маркетплейсах",
        "raw_text": "Это важная статья о том, как продавать на маркетплейсах",
        "url": "https://vc.ru/marketplace-news",
        "source": "VC.ru",
        "category": "general"
    }
    
    item_stop_signal = {
        "id": 7,
        "title": "Поздравляем победителей рейтинга селлеров",
        "description": "Опубликован ежегодный рейтинг лучших селлеров",
        "raw_text": "Поздравляем победителей рейтинга! Это большое событие для сообщества. Победители получат призы и возможность развивать свой бизнес на маркетплейсах.",
        "url": "https://marketplace-awards.ru/winners",
        "source": "Awards",
        "category": "general"
    }
    
    item_strong_relevance = {
        "id": 8,
        "title": "Wildberries изменил условия оферты для селлеров",
        "description": "Маркетплейс Wildberries обновил оферту и повысил комиссию на 3%",
        "raw_text": "Wildberries объявил об изменении условий оферты. Комиссия на категорию одежда повышается с 12% до 15%. Изменения вступают в силу с 1 мая. Селлерам необходимо ознакомиться с новыми условиями доставки и хранения на складе.",
        "url": "https://wildberries.ru/services/seller-offer",
        "source": "WB News",
        "category": "general"
    }
    
    item_interview = {
        "id": 9,
        "title": "Интервью с главой Ozon",
        "description": "Глава Ozon рассказал о планах развития",
        "raw_text": "Интервью с генеральным директором Ozon о будущем компании",
        "url": "https://example.com/interview",
        "source": "Interview",
        "category": "general"
    }
    
    return {
        "sample_item_with_url": sample_item_with_url,
        "item_no_url": item_no_url,
        "item_short_text": item_short_text,
        "item_no_marketplace_context": item_no_marketplace_context,
        "item_no_impact": item_no_impact,
        "item_blacklist_domain": item_blacklist_domain,
        "item_stop_signal": item_stop_signal,
        "item_strong_relevance": item_strong_relevance,
        "item_interview": item_interview
    }


class TestFailClosed:
    """Tests for fail-closed behavior."""

    def test_empty_passed_slots_skip(self):
        """If no candidates pass gate, slot should be skipped."""
        try:
            from preview_staging import run_regular_preview
        except ImportError:
            from staging.preview_staging import run_regular_preview
            
        from unittest.mock import patch, MagicMock

        mock_pending = [
            {"id": 1, "title": "Погода", "description": "Солнечно", "raw_text": "Погода хорошая", "url": "https://a.ru"},
            {"id": 2, "title": "Концерт", "description": "Музыка", "raw_text": "Концерт был", "url": "https://b.ru"},
]

        with patch("preview_staging.get_pending_news", return_value=mock_pending):
            with patch("preview_staging.get_all_pending_count", return_value=2):
                with patch("preview_staging.init_db"):
                    with patch("preview_staging.select_best_items_for_publishing") as mock_select:
                        mock_select.return_value = None
                        with patch("preview_staging.ensure_staging_output_dir"):
                            with patch("builtins.open", MagicMock()):
                                run_regular_preview()
                                mock_select.assert_not_called()
