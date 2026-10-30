import unittest

from deck.textfit import fit_stack, fit_text, measure, wrap_text


class TextfitTest(unittest.TestCase):
    def test_cjk_is_one_em(self):
        self.assertAlmostEqual(wrap_text("中文", 20, 100)[0], "中文")
        lines = wrap_text("中" * 10, 20, 100)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(len(line) <= 5 for line in lines))

    def test_wrap_keeps_words(self):
        lines = wrap_text("hello world this is a test", 12, 120)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(measure(line, 12), 121)

    def test_fit_shrinks(self):
        size, lines, ok = fit_text("中" * 40, 200, 300, 40, 12)
        self.assertTrue(ok)
        self.assertLess(size, 40)
        self.assertGreaterEqual(size, 12)

    def test_fit_reports_overflow(self):
        size, lines, ok = fit_text("中" * 500, 100, 40, 20, 10)
        self.assertFalse(ok)
        self.assertEqual(size, 10)
        self.assertTrue(lines)

    def test_fit_stack_uses_one_size(self):
        size, wrapped, ok = fit_stack(["第一条要点" * 2, "第二条要点", "第三条要点"], 200, 400, 24, 10, 10)
        self.assertTrue(ok)
        self.assertEqual(len(wrapped), 3)
        self.assertLessEqual(size, 24)

    def test_min_never_above_max(self):
        size, _, ok = fit_text("页脚", 200, 20, 8.5, 9)
        self.assertTrue(ok)
        self.assertEqual(size, 8.5)


if __name__ == "__main__":
    unittest.main()
