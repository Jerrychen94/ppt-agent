import unittest
from pathlib import Path

from PIL import Image

from deck.layouts import build_scene
from deck.model import LAYOUTS
from deck.theme import load_theme
from support import slide

TMP = Path("tmp/tests")
IMAGE = TMP / "sample.png"


def setUpModule():
    TMP.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1200, 800), (40, 90, 160)).save(IMAGE)


class LayoutTest(unittest.TestCase):
    def setUp(self):
        self.theme = load_theme("swiss")

    def test_all_layouts_build(self):
        for layout in LAYOUTS:
            with self.subTest(layout=layout):
                data = slide(layout, image=str(IMAGE) if layout == "image" else "")
                scene = build_scene(data, self.theme, 2, 5, "测试 deck")
                self.assertGreater(len(scene.elements), 0)
                codes = [w["code"] for w in scene.warnings]
                self.assertNotIn("OVERFLOW", codes)
                self.assertNotIn("IMAGE_NOT_FOUND", codes)
                self.assertEqual(scene.notes, data["notes"])

    def test_elements_stay_in_bounds(self):
        for layout in LAYOUTS:
            data = slide(layout, image=str(IMAGE) if layout == "image" else "")
            scene = build_scene(data, self.theme, 2, 5, "测试 deck")
            for element in scene.elements:
                if type(element).__name__ == "Line":
                    xs, ys = (element.x1, element.x2), (element.y1, element.y2)
                    self.assertGreaterEqual(min(xs), 0, layout)
                    self.assertGreaterEqual(min(ys), 0, layout)
                    self.assertLessEqual(max(xs), 13.34, layout)
                    self.assertLessEqual(max(ys), 7.51, layout)
                else:
                    self.assertGreaterEqual(element.x, 0, layout)
                    self.assertGreaterEqual(element.y, 0, layout)
                    self.assertLessEqual(element.x + element.w, 13.34, layout)
                    self.assertLessEqual(element.y + element.h, 7.51, layout)

    def test_image_missing_warns(self):
        scene = build_scene(slide("image", image="nope.png"), self.theme, 2, 5, "x")
        self.assertIn("IMAGE_NOT_FOUND", [w["code"] for w in scene.warnings])

    def test_stats_falls_back(self):
        scene = build_scene(slide("stats", stats=[]), self.theme, 2, 5, "x")
        self.assertIn("LAYOUT_FALLBACK", [w["code"] for w in scene.warnings])


if __name__ == "__main__":
    unittest.main()
