"""Smoke tests for filters.py"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from filters import is_important, should_ignore, filter_news


class TestFilters:
    """Basic tests for filters module."""

    def test_is_important_finds_marketplace(self):
        """is_important should detect marketplace keywords."""
        text = "Ozon повысил комиссию"
        assert is_important(text) is True

    def test_is_important_finds_logistics(self):
        """is_important should detect logistics keywords."""
        text = "доставка и логистика"
        assert is_important(text) is True

    def test_is_important_finds_rules(self):
        """is_important should detect rules/regulation keywords."""
        text = "новые правила маркетплейсов"
        assert is_important(text) is True

    def test_is_important_rejects_generic(self):
        """is_important should reject generic news."""
        text = "Погода сегодня хорошая"
        assert is_important(text) is False

    def test_should_ignore_finds_events(self):
        """should_ignore should detect event keywords."""
        text = "конференция маркетплейсов"
        assert should_ignore(text) is True

    def test_should_ignore_finds_politics(self):
        """should_ignore should detect political keywords."""
        text = "политика и экономика"
        assert should_ignore(text) is True

    def test_filter_news_passes_relevant(self):
        """filter_news should pass relevant marketplace news."""
        title = "Ozon изменил тарифы"
        description = "Комиссия повышена"
        link = "https://ozon.ru"
        assert filter_news(title, description, link) is True

    def test_filter_news_rejects_generic(self):
        """filter_news should reject generic news."""
        title = "Новости культуры"
        description = "Выставка открылась"
        link = "https://example.ru"
        assert filter_news(title, description, link) is False
