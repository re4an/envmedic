import tempfile
import unittest
from pathlib import Path

from envmedic.parser import parse_file, parse_text


class ParserTests(unittest.TestCase):
    def values(self, text):
        return parse_text(text).as_dict()

    def test_basic_pairs(self):
        self.assertEqual(self.values("A=1\nB=two"), {"A": "1", "B": "two"})

    def test_comments_and_blank_lines_skipped(self):
        result = parse_text("# hi\n\nA=1\n   # indented comment\n")
        self.assertEqual(result.as_dict(), {"A": "1"})
        self.assertEqual(result.issues, [])

    def test_export_prefix(self):
        self.assertEqual(self.values("export A=1"), {"A": "1"})
        self.assertEqual(self.values("export=5"), {"export": "5"})

    def test_spaces_around_equals(self):
        self.assertEqual(self.values("A = 1"), {"A": "1"})

    def test_equals_inside_value(self):
        self.assertEqual(self.values("URL=http://x?a=b"), {"URL": "http://x?a=b"})

    def test_double_quotes_and_escapes(self):
        self.assertEqual(self.values('A="hello world"'), {"A": "hello world"})
        self.assertEqual(self.values(r'B="line\nbreak"'), {"B": "line\nbreak"})
        self.assertEqual(self.values(r'C="say \"hi\""'), {"C": 'say "hi"'})

    def test_single_quotes_are_literal(self):
        self.assertEqual(self.values(r"A='no\nescape'"), {"A": r"no\nescape"})

    def test_inline_comments(self):
        self.assertEqual(self.values("A=value # comment"), {"A": "value"})
        self.assertEqual(self.values("A=val#ue"), {"A": "val#ue"})
        self.assertEqual(self.values('A="x # y" # c'), {"A": "x # y"})

    def test_empty_values(self):
        self.assertEqual(self.values("A="), {"A": ""})
        self.assertEqual(self.values("A=# just a comment"), {"A": ""})
        self.assertEqual(self.values('A=""'), {"A": ""})

    def test_unterminated_quote(self):
        result = parse_text('A="oops')
        self.assertEqual(result.entries, [])
        self.assertEqual(result.issues[0].line, 1)
        self.assertIn("unterminated", result.issues[0].message)

    def test_text_after_closing_quote(self):
        result = parse_text('A="x" y')
        self.assertEqual(result.entries, [])
        self.assertEqual(len(result.issues), 1)

    def test_invalid_lines(self):
        result = parse_text("not a pair\n1A=x\nOK=1")
        self.assertEqual([i.line for i in result.issues], [1, 2])
        self.assertEqual(result.as_dict(), {"OK": "1"})

    def test_duplicates_last_wins(self):
        result = parse_text("A=1\nA=2")
        self.assertEqual(len(result.entries), 2)
        self.assertEqual(result.as_dict(), {"A": "2"})

    def test_crlf(self):
        self.assertEqual(self.values("A=1\r\nB=2\r\n"), {"A": "1", "B": "2"})

    def test_line_numbers(self):
        result = parse_text("# c\n\nA=1\nB=2")
        self.assertEqual([(e.key, e.line) for e in result.entries], [("A", 3), ("B", 4)])

    def test_bom_is_stripped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_bytes(b"\xef\xbb\xbfA=1\n")
            self.assertEqual(parse_file(path).as_dict(), {"A": "1"})


if __name__ == "__main__":
    unittest.main()
