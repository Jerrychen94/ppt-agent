import unittest

from deck.errors import StageError
from deck.model import normalize_brief, validate_deck, validate_outline
from support import BRIEF, deck


class BriefTest(unittest.TestCase):
    def test_defaults_and_roundtrip(self):
        brief = normalize_brief({"topic": "季度复盘"})
        self.assertEqual(brief["language"], "zh")
        self.assertEqual(brief["slide_count"], 10)
        self.assertEqual(brief["theme"], "swiss")

    def test_empty_topic(self):
        with self.assertRaises(StageError) as ctx:
            normalize_brief({"topic": "   "})
        self.assertEqual(ctx.exception.code, "EMPTY_TOPIC")

    def test_slide_count_range(self):
        for value in (2, 31):
            with self.assertRaises(StageError) as ctx:
                normalize_brief({"topic": "x", "slide_count": value})
            self.assertEqual(ctx.exception.code, "INVALID_SLIDE_COUNT")

    def test_section_without_points(self):
        with self.assertRaises(StageError) as ctx:
            normalize_brief({"topic": "x", "sections": [{"title": "背景", "points": []}]})
        self.assertEqual(ctx.exception.code, "EMPTY_SECTION")

    def test_long_point(self):
        with self.assertRaises(StageError) as ctx:
            normalize_brief({"topic": "x", "key_points": ["长" * 61]})
        self.assertEqual(ctx.exception.code, "FIELD_TOO_LONG")


class OutlineTest(unittest.TestCase):
    def test_inserts_cover_and_closing(self):
        outline, fixes = validate_outline(
            {"title": "标题", "slides": [{"layout": "bullets", "title": "第一页", "points": ["a"]}]}, normalize_brief(BRIEF)
        )
        self.assertEqual(outline["slides"][0]["layout"], "title")
        self.assertEqual(outline["slides"][-1]["layout"], "closing")
        self.assertIn("补封面", fixes)

    def test_unknown_layout(self):
        with self.assertRaises(StageError) as ctx:
            validate_outline(
                {
                    "slides": [
                        {"layout": "title", "title": "封面", "points": []},
                        {"layout": "hero", "title": "未知版式", "points": []},
                        {"layout": "closing", "title": "谢谢", "points": []},
                    ]
                },
                normalize_brief(BRIEF),
            )
        self.assertEqual(ctx.exception.code, "INVALID_LAYOUT")


class DeckTest(unittest.TestCase):
    def test_normalizes_bullets(self):
        data = deck()
        data["slides"][1]["bullets"] = [{"text": "字典写法"}, "字符串写法"]
        result = validate_deck(data)
        self.assertEqual(result["slides"][1]["bullets"], ["字典写法", "字符串写法"])
        self.assertEqual(result["meta"]["slide_count"], 4)

    def test_rejects_unknown_layout(self):
        data = deck()
        data["slides"][1]["layout"] = "hero"
        with self.assertRaises(StageError) as ctx:
            validate_deck(data)
        self.assertEqual(ctx.exception.code, "INVALID_LAYOUT")


if __name__ == "__main__":
    unittest.main()
