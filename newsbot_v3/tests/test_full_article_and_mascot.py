import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "newsbot_v2"))
import full_article_callback_worker as worker
from newsbot_v3.tools.prepare_mascot_assets import prepare, select_mascot_asset


class FullArticleTests(unittest.TestCase):
    @mock.patch.object(worker, "answer_callback")
    @mock.patch.object(worker, "mark_expanded")
    @mock.patch.object(worker, "already_expanded", return_value=False)
    @mock.patch.object(worker, "edit_message_to_full_article", return_value=({}, True))
    @mock.patch.object(worker, "get_max_message_id", return_value="55")
    @mock.patch.object(worker, "get_article", return_value=(1, "t", "raw", "https://x", "https://s", "55"))
    def test_edit_original_when_mid_present(self, *_):
        self.assertTrue(worker.expand_full_article(1, "cb", "77", "99"))

    def test_raw_text_fallback_and_source_plain_text(self):
        msg = worker.build_full_article_message((1, "t", "raw body", "https://link", "https://source", "5"))
        self.assertIn("raw body", msg)
        self.assertIn("Источник: https://source", msg)
        self.assertIn("https://link", msg)


class MascotTests(unittest.TestCase):
    @unittest.skipIf(Image is None, "Pillow is not installed in this environment")
    def _build_zip(self, zip_path: Path, missing=None):
        from newsbot_v3.tools.prepare_mascot_assets import REQUIRED

        with zipfile.ZipFile(zip_path, "w") as zf:
            for f in REQUIRED.values():
                if missing and f in missing:
                    continue
                with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
                    Image.new("RGBA", (1500, 900), (255, 0, 0, 120)).save(tmp.name)
                    zf.write(tmp.name, arcname=f)
            zf.writestr("README.txt", "readme")
            zf.writestr("manifest.csv", "k,v")

    @unittest.skipIf(Image is None, "Pillow is not installed in this environment")
    def test_prepare_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            zip_path = Path(td) / "m.zip"
            out = Path(td) / "out"
            self._build_zip(zip_path)
            prepare(zip_path, out)
            prepare(zip_path, out)
            data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("base", data)
            self.assertTrue((out / "source" / "README.txt").exists())
            self.assertTrue((out / "source" / "manifest.csv").exists())
            self.assertTrue((out / "web" / data["base"]["source_filename"]).exists())
            self.assertTrue((out / "mobile" / data["base"]["source_filename"]).exists())
            self.assertEqual(select_mascot_asset("unknown kind", data)["key"], "base")
            self.assertEqual(select_mascot_asset("morning digest", data)["key"], "morning_digest")
            self.assertEqual(select_mascot_asset("final digest", data)["key"], "evening_digest")
            self.assertEqual(select_mascot_asset("audio digest", data)["key"], "audio_digest")
            self.assertEqual(select_mascot_asset("urgent", data)["key"], "important")

    @unittest.skipIf(Image is None, "Pillow is not installed in this environment")
    def test_missing_source_file_fails(self):
        with tempfile.TemporaryDirectory() as td:
            zip_path = Path(td) / "m.zip"
            out = Path(td) / "out"
            self._build_zip(zip_path, missing={"01_Friendly_Approved_Style_Base.png"})
            with self.assertRaises(RuntimeError):
                prepare(zip_path, out)


if __name__ == "__main__":
    unittest.main()

def test_v3_selector_mapping_contract():
    from newsbot_v3.app.visual.mascot_assets import select_mascot_kind
    assert select_mascot_kind(post_kind='regular', tags=['urgent']) == 'urgent_important'
    assert select_mascot_kind(post_kind='regular', title='market analysis') == 'analytics'
    assert select_mascot_kind(post_kind='regular', text='налоги и закон') == 'law_taxes'
    assert select_mascot_kind(post_kind='regular', text='маркировка честный знак') == 'marking_compliance'
    assert select_mascot_kind(post_kind='regular', text='тарифы и комиссии выплаты') == 'money_profit'
    assert select_mascot_kind(post_kind='regular', text='интересная новость') == 'interesting_news'
    assert select_mascot_kind(post_kind='digest', digest_kind='morning') == 'morning_digest'
    assert select_mascot_kind(post_kind='digest', digest_kind='final') == 'evening_digest'
    assert select_mascot_kind(post_kind='audio', audio_digest_kind='audio_digest') == 'audio_digest'
