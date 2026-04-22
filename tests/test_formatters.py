"""Smoke tests for formatters.py"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from formatters import (
    get_item_url,
    get_topic_emoji,
    get_hashtags,
    get_summary,
    get_insight,
    format_news,
    detect_link_type,
    get_source_link
)


class TestFormatters:
    """Basic tests for formatters module."""

    def test_get_item_url_prefers_url(self):
        """get_item_url should prefer 'url' field."""
        item = {"url": "https://ozon.ru", "link": "https://old.ru"}
        assert get_item_url(item) == "https://ozon.ru"

    def test_get_item_url_falls_back_to_link(self):
        """get_item_url should fall back to 'link' field."""
        item = {"link": "https://link.ru"}
        assert get_item_url(item) == "https://link.ru"

    def test_get_item_url_empty(self):
        """get_item_url should return empty string for empty item."""
        assert get_item_url({}) == ""

    def test_get_topic_emoji_commission(self):
        """get_topic_emoji should detect commission keywords."""
        emoji = get_topic_emoji("Комиссия повышена", "Описание")
        assert emoji == "💰"

    def test_get_topic_emoji_logistics(self):
        """get_topic_emoji should detect logistics keywords."""
        emoji = get_topic_emoji("Доставка изменена", "Описание")
        assert emoji == "🚚"

    def test_get_topic_emoji_default(self):
        """get_topic_emoji should return default emoji."""
        emoji = get_topic_emoji("Generic title", "Description")
        assert emoji == "📦"

    def test_get_hashtags_ozon(self):
        """get_hashtags should detect Ozon."""
        tags = get_hashtags("Ozon news", "Description", "Ozon")
        assert "озон" in tags or "ozon" in tags

    def test_get_hashtags_wildberries(self):
        """get_hashtags should detect Wildberries."""
        tags = get_hashtags("Wildberries", "Description", "WB")
        assert "wildberries" in tags or "вилдберриз" in tags

    def test_get_summary_truncates(self):
        """get_summary should truncate long text."""
        long_text = "A" * 300
        result = get_summary(long_text)
        assert len(result) <= 200

    def test_get_summary_empty(self):
        """get_summary should handle empty input."""
        assert get_summary("") == ""
        assert get_summary(None) == ""

    def test_get_insight_increase(self):
        """get_insight should detect increase keywords."""
        insight = get_insight("Комиссия повышена", "Описание")
        assert "изменение" in insight.lower()

    def test_get_insight_block(self):
        """get_insight should detect block/ban keywords."""
        insight = get_insight("Аккаунт заблокирован", "Описание")
        assert "риск" in insight.lower() or "блокир" in insight.lower()

    def test_format_news_returns_string(self):
        """format_news should return a string."""
        item = {
            "title": "Test Title",
            "description": "Test Description",
            "source": "Test Source",
            "url": "https://test.ru"
        }
        result = format_news(item)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_news_contains_title(self):
        """format_news should contain title."""
        item = {
            "title": "Ozon комиссия",
            "description": "Изменение",
            "source": "Ozon",
            "url": "https://ozon.ru"
        }
        result = format_news(item)
        assert "Ozon комиссия" in result

    def test_detect_link_type_official(self):
        """detect_link_type should return 'official' for marketplace domains."""
        assert detect_link_type({"url": "https://seller.ozon.ru"}) == "official"
        assert detect_link_type({"url": "https://portal.wildberries.ru"}) == "official"
        assert detect_link_type({"url": "https://business.ozon.ru"}) == "official"

    def test_detect_link_type_forum(self):
        """detect_link_type should return 'forum' for forum domains."""
        assert detect_link_type({"url": "https://telega.in"}) == "forum"
        assert detect_link_type({"url": "https://teletype.in"}) == "forum"
        assert detect_link_type({"url": "https://forum.seller"}) == "forum"

    def test_detect_link_type_media(self):
        """detect_link_type should return 'media' for other domains."""
        assert detect_link_type({"url": "https://news.ru"}) == "media"
        assert detect_link_type({"url": "https://rbc.ru"}) == "media"

    def test_detect_link_type_empty(self):
        """detect_link_type should return 'media' for empty link."""
        assert detect_link_type({}) == "media"

    def test_get_source_link_official_wins(self):
        """get_source_link should prefer official_url over other sources."""
        item = {
            "url": "https://news.ru",
            "official_url": "https://seller.ozon.ru"
        }
        link, link_type = get_source_link(item)
        assert link == "https://seller.ozon.ru"
        assert link_type == "official"

    def test_get_source_link_url_wins_over_link(self):
        """get_source_link should prefer url over link field."""
        item = {
            "url": "https://news.ru",
            "link": "https://old.ru"
        }
        link, link_type = get_source_link(item)
        assert link == "https://news.ru"

    def test_get_source_link_uses_forum_url(self):
        """get_source_link should use forum_url when no official."""
        item = {
            "link": "https://telega.in/topic",
            "forum_url": "https://forum.seller/topic"
        }
        link, link_type = get_source_link(item)
        assert link_type == "forum"

    def test_get_source_link_empty(self):
        """get_source_link should return empty for empty item."""
        link, link_type = get_source_link({})
        assert link == ""
        assert link_type == "media"
