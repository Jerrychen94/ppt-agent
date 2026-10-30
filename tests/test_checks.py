import unittest

from deck.checks import qa
from deck.theme import THEMES, contrast, load_theme
from support import deck


def codes(report: dict) -> list[str]:
    return [item["code"] for item in report["findings"]]


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.theme = load_theme("swiss")

    def test_clean(self):
        report = qa(deck(), self.theme)
        self.assertTrue(report["ok"])
        self.assertEqual(report["stats"]["slides"], 4)

    def test_long_title(self):
        data = deck()
        data["slides"][0]["title"] = "超长标题" * 12
        report = qa(data, self.theme)
        self.assertFalse(report["ok"])
        self.assertIn("TITLE_TOO_LONG", codes(report))

    def test_overflow(self):
        data = deck()
        data["slides"][0]["title"] = "溢出" * 200
        report = qa(data, self.theme)
        self.assertIn("OVERFLOW", codes(report))

    def test_missing_notes_and_duplicate(self):
        data = deck(notes=False)
        data["slides"][2]["title"] = data["slides"][1]["title"]
        report = qa(data, self.theme)
        self.assertIn("MISSING_NOTES", codes(report))
        self.assertIn("DUPLICATE_TITLE", codes(report))
        self.assertTrue(report["ok"])

    def test_empty_content(self):
        data = deck()
        data["slides"][1]["bullets"] = []
        report = qa(data, self.theme)
        self.assertIn("EMPTY_CONTENT", codes(report))
        self.assertFalse(report["ok"])

    def test_theme_contrast(self):
        for name, theme in THEMES.items():
            with self.subTest(theme=name):
                self.assertEqual(theme.check(), [])
                self.assertGreaterEqual(contrast(theme.fg, theme.bg), 4.5)


if __name__ == "__main__":
    unittest.main()
