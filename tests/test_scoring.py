"""Smoke tests for scoring.py"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scoring import (
    calculate_score,
    is_noise,
    normalize_title,
    score_item,
    SCORE_WEIGHTS,
    MIN_SCORE_THRESHOLD
)


class TestScoring:
    """Basic tests for scoring module."""

    def test_calculate_score_marketplace(self):
        """calculate_score should detect marketplace keywords."""
        score, bucket, tags = calculate_score("Ozon повысил комиссию", "Важная новость")
        assert score > 0
        assert "marketplace" in tags or "commission" in tags

    def test_calculate_score_court(self):
        """calculate_score should detect court/legal keywords."""
        score, bucket, tags = calculate_score("Суд оштрафовал Ozon", "Арбитражный суд")
        assert score > 20
        assert "court" in tags or "fine" in tags

    def test_calculate_score_logistics(self):
        """calculate_score should detect logistics keywords."""
        score, bucket, tags = calculate_score("Изменения в доставке", "Логистика")
        assert score > 0

    def test_calculate_score_returns_tuple(self):
        """calculate_score should return tuple of (score, bucket, tags)."""
        result = calculate_score("Test", "Description")
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], int)
        assert isinstance(result[1], str)
        assert isinstance(result[2], list)

    def test_is_noise_conference(self):
        """is_noise should detect conference events."""
        assert is_noise("Конференция маркетплейсов", "Описание") is True

    def test_is_noise_politics(self):
        """is_noise should detect political content."""
        assert is_noise("Политика правительства", "Новости") is True

    def test_is_noise_not_marketplace_news(self):
        """is_noise should NOT reject marketplace news."""
        assert is_noise("Ozon изменил тарифы", "Комиссия повышена") is False

    def test_normalize_title(self):
        """normalize_title should clean up titles."""
        result = normalize_title("  Test   Title  ")
        assert result == "Test Title"

    def test_normalize_title_truncates_long(self):
        """normalize_title should truncate long titles."""
        long_title = "A" * 300
        result = normalize_title(long_title)
        assert len(result) <= 200

    def test_score_item_adds_fields(self):
        """score_item should add score, priority_bucket, reason_tags."""
        item = {"title": "Ozon комиссия", "description": "Изменение"}
        result = score_item(item)
        assert "score" in result
        assert "priority_bucket" in result
        assert "reason_tags" in result
        assert result["score"] > 0

    def test_score_weights_exist(self):
        """SCORE_WEIGHTS should have expected keys."""
        assert "marketplace" in SCORE_WEIGHTS
        assert "court" in SCORE_WEIGHTS
        assert "regulation" in SCORE_WEIGHTS

    def test_min_score_threshold_is_int(self):
        """MIN_SCORE_THRESHOLD should be an integer."""
        assert isinstance(MIN_SCORE_THRESHOLD, int)
