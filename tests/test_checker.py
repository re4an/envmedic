import unittest

from envmedic.checker import check
from envmedic.parser import parse_text


def run(env_text, example_text):
    return check(parse_text(env_text), parse_text(example_text))


class CheckerTests(unittest.TestCase):
    def test_everything_matches(self):
        report = run("A=1\nB=2", "A=\nB=")
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.warning_count, 0)
        self.assertFalse(report.has_problems())
        self.assertFalse(report.has_problems(strict=True))

    def test_missing_keys_keep_example_order(self):
        report = run("B=1", "A=\nB=\nC=")
        self.assertEqual(report.missing, ["A", "C"])
        self.assertTrue(report.has_problems())

    def test_extra_keys_are_warnings(self):
        report = run("A=1\nZ=9", "A=")
        self.assertEqual(report.extra, ["Z"])
        self.assertFalse(report.has_problems())
        self.assertTrue(report.has_problems(strict=True))

    def test_empty_values_are_warnings(self):
        report = run("A=\nB=2", "A=\nB=")
        self.assertEqual(report.empty, ["A"])
        self.assertFalse(report.has_problems())
        self.assertTrue(report.has_problems(strict=True))

    def test_empty_extra_key_not_reported_as_empty(self):
        report = run("Z=", "A=x")
        self.assertEqual(report.empty, [])
        self.assertEqual(report.extra, ["Z"])

    def test_duplicates_report_all_lines(self):
        report = run("A=1\nB=2\nA=3", "A=\nB=")
        self.assertEqual(report.duplicates, {"A": [1, 3]})
        self.assertTrue(report.has_problems())

    def test_syntax_problems_from_both_files(self):
        report = run("garbage", "A=\nalso garbage")
        files = sorted((p.file, p.line) for p in report.syntax)
        self.assertEqual(files, [(".env", 1), (".env.example", 2)])
        self.assertTrue(report.has_problems())

    def test_as_dict(self):
        data = run("A=1", "A=\nB=").as_dict()
        self.assertEqual(data["missing"], ["B"])
        self.assertEqual(data["errors"], 1)
        self.assertFalse(data["ok"])


if __name__ == "__main__":
    unittest.main()
