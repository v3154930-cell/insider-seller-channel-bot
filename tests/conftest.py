"""Pytest configuration and shared fixtures for staging tests."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture
def sample_item_with_url():
    """Sample item with valid URL."""
    return {
        "id": 1,
        "title": "Ozon повысил комиссию на категорию 电子",
        "description": "Маркетплейс Ozon объявил о повышении комиссии на 5%",
        "raw_text": "Ozon повысил комиссию на категорию электроника с 15% до 20%. Это коснется всех селлеров, работающих по модели FBS.",
        "url": "https://www.ozon.ru/info/commission-change/",
        "source": "Ozon News",
        "category": "general"
    }


@pytest.fixture
def item_no_url():
    """Item without URL."""
    return {
        "id": 2,
        "title": "Новость без ссылки",
        "description": "Какое-то важное событие",
        "raw_text": "Произошло важное событие для селлеров",
        "url": "",
        "source": "Test Source",
        "category": "general"
    }


@pytest.fixture
def item_short_text():
    """Item with too short text."""
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
    """Item without marketplace context."""
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
    """Item with marketplace context but no practical impact."""
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
    """Item from blacklisted domain."""
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
    """Item with stop signal ( поздравления, рейтинг и т.д.)."""
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
    """Item that should pass the gate - strong relevance."""
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
    """Item with stop signal - интервью."""
    return {
        "id": 9,
        "title": "Интервью с главой Ozon",
        "description": "Глава Ozon рассказал о планах развития",
        "raw_text": "Интервью с генеральным директором Ozon о будущем компании",
        "url": "https://example.com/interview",
        "source": "Interview",
        "category": "general"
    }
