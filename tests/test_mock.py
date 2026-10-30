import unittest

from deck import mock
from deck.model import normalize_brief
from support import BRIEF


class MockTest(unittest.TestCase):
    def test_slide_counts_are_exact(self):
        for count in (3, 4, 6, 9, 10, 20, 30):
            with self.subTest(count=count):
                brief = normalize_brief({**BRIEF, "slide_count": count})
                outline = mock.build_outline(brief)
                self.assertEqual(len(outline["slides"]), count)
                self.assertEqual(outline["slides"][0]["layout"], "title")
                self.assertEqual(outline["slides"][-1]["layout"], "closing")

    def test_compose_fills_notes_and_limits(self):
        brief = normalize_brief(BRIEF)
        outline = mock.build_outline(brief)
        deck = mock.compose_deck(brief, outline)
        self.assertEqual(len(deck["slides"]), 9)
        for slide in deck["slides"]:
            self.assertGreaterEqual(len(slide["notes"]), 20, slide["title"])
            self.assertLessEqual(len(slide["bullets"]), 5, slide["title"])
            self.assertLessEqual(len(slide["title"]), 30, slide["title"])

    def test_without_key_points(self):
        brief = normalize_brief({"topic": "没有要点的周报", "slide_count": 6})
        outline = mock.build_outline(brief)
        deck = mock.compose_deck(brief, outline)
        self.assertEqual(len(deck["slides"]), 6)


if __name__ == "__main__":
    unittest.main()
