import unittest
from pathlib import Path

from PIL import Image

from deck.checks import qa
from deck.render import build_scenes, render_html, render_markdown, render_pptx
from deck.theme import load_theme
from support import deck

TMP = Path("tmp/tests/render")


class RenderTest(unittest.TestCase):
    def setUp(self):
        TMP.mkdir(parents=True, exist_ok=True)
        self.deck = deck()
        self.theme = load_theme("swiss")

    def test_pptx_roundtrip(self):
        path = TMP / "deck.pptx"
        info = render_pptx(self.deck, self.theme, path)
        self.assertEqual(info["slides"], 4)
        self.assertEqual(info["notes_count"], 4)
        self.assertEqual(info["titles"][0], "有效的汇报长什么样")
        self.assertGreater(info["bytes"], 10_000)

    def test_html_and_markdown(self):
        html_path = TMP / "preview.html"
        md_path = TMP / "deck.md"
        render_html(self.deck, self.theme, html_path)
        render_markdown(self.deck, md_path)
        page = html_path.read_text(encoding="utf-8")
        self.assertIn("有效的汇报长什么样", page)
        self.assertIn("width:1280px", page)
        text = md_path.read_text(encoding="utf-8")
        self.assertIn("## 01.", text)
        self.assertIn("讲稿", text)

    def test_scenes_share_geometry(self):
        scenes = build_scenes(self.deck, self.theme)
        self.assertEqual(len(scenes), 4)
        self.assertEqual(scenes[0].layout, "title")
        self.assertGreater(len(scenes[1].elements), 3)

    def test_clean_deck_scores_100(self):
        report = qa(self.deck, self.theme)
        self.assertTrue(report["ok"])
        self.assertEqual(report["score"], 100)

    def test_image_is_embedded(self):
        image = TMP / "embedded.png"
        if not image.exists():
            Image.new("RGB", (900, 600), (30, 80, 140)).save(image)
        data = deck()
        data["slides"][1]["layout"] = "image"
        data["slides"][1]["image"] = str(image)
        pptx_path = TMP / "image.pptx"
        info = render_pptx(data, self.theme, pptx_path)
        self.assertGreater(info["bytes"], 20_000)
        html_path = TMP / "image.html"
        render_html(data, self.theme, html_path)
        self.assertIn("data:image/png;base64", html_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
