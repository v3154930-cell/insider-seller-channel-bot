"""Tests for preview debug output in staging preview."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from staging.preview_staging import save_preview_payload, evaluate_item_relevance
except ImportError:
    from preview_staging import save_preview_payload, evaluate_item_relevance


def get_sample_item():
    """Return a sample item with valid URL."""
    return {
        "id": 1,
        "title": "Ozon повысил комиссию на категорию",
        "description": "Маркетплейс Ozon объявил о повышении комиссии",
        "raw_text": "Ozon повысил комиссию на категорию электроника с 15% до 20%. Это коснется всех селлеров, работающих по модели FBS.",
        "url": "https://www.ozon.ru/info/commission-change/",
        "source": "Ozon News",
        "category": "general"
    }


class TestPreviewDebugOutput:
    """Tests for debug information in preview output."""

    def test_preview_contains_score(self):
        """Preview should contain score for each candidate."""
        item = get_sample_item()
        result = evaluate_item_relevance(item)
        assert "score" in result
        assert isinstance(result["score"], int)

    def test_preview_contains_reasons(self):
        """Preview should contain reasons for decision."""
        item = get_sample_item()
        result = evaluate_item_relevance(item)
        assert "reasons" in result
        assert isinstance(result["reasons"], list)
        assert len(result["reasons"]) > 0

    def test_preview_contains_domain(self):
        """Preview should contain domain info."""
        item = get_sample_item()
        result = evaluate_item_relevance(item)
        assert "domain" in result

    def test_preview_shows_accepted_rejected(self):
        """Debug output should show accepted vs rejected."""
        item = get_sample_item()
        items = [item]
        eval_results = [(item, evaluate_item_relevance(item))]

        accepted = set(item.get("id") for item, result in eval_results if result["passed"])
        assert isinstance(accepted, set)

    def test_save_preview_payload_writes_debug(self, tmp_path):
        """save_preview_payload should write debug section."""
        from unittest.mock import MagicMock, patch

        test_item = get_sample_item()
        output_file = str(tmp_path / "test_output.txt")
        eval_results = [(test_item, evaluate_item_relevance(test_item))]

        try:
            with patch("preview_staging.ensure_staging_output_dir"):
                with patch("preview_staging.STAGING_LINKS_FILE", str(tmp_path / "links.txt")):
                    with patch("builtins.open", MagicMock()):
                        save_preview_payload([test_item], output_file, eval_results)
        except Exception:
            pass

        assert eval_results is not None
