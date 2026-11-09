import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from envmedic.cli import format_value, main
from envmedic.parser import parse_text


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.env = self.dir / ".env"
        self.example = self.dir / ".env.example"

    def args(self, *extra):
        return [extra[0], "--env", str(self.env), "--example", str(self.example), *extra[1:]]

    def test_check_passes(self):
        self.env.write_text("A=1\n")
        self.example.write_text("A=\n")
        code, out, _ = run(self.args("check"))
        self.assertEqual(code, 0)
        self.assertIn("OK: 0 error(s), 0 warning(s)", out)

    def test_check_fails_on_missing(self):
        self.env.write_text("A=1\n")
        self.example.write_text("A=\nB=\n")
        code, out, _ = run(self.args("check"))
        self.assertEqual(code, 1)
        self.assertIn("missing from", out)
        self.assertIn("- B", out)
        self.assertIn("FAILED: 1 error(s)", out)

    def test_strict_fails_on_warnings(self):
        self.env.write_text("A=\n")
        self.example.write_text("A=\n")
        self.assertEqual(run(self.args("check"))[0], 0)
        code, out, _ = run(self.args("check", "--strict"))
        self.assertEqual(code, 1)
        self.assertIn("[strict]", out)

    def test_json_output(self):
        self.env.write_text("A=1\nA=2\n")
        self.example.write_text("A=\nB=\n")
        code, out, _ = run(self.args("check", "--format", "json"))
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(data["missing"], ["B"])
        self.assertEqual(data["duplicates"], {"A": [1, 2]})
        self.assertFalse(data["ok"])

    def test_missing_files_exit_2(self):
        self.example.write_text("A=\n")
        code, _, err = run(self.args("check"))
        self.assertEqual(code, 2)
        self.assertIn("file not found", err)

    def test_sync_appends_missing_keys(self):
        self.env.write_text("A=x")  # no trailing newline on purpose
        self.example.write_text("A=1\nB=hello world\nC=\n")
        code, out, _ = run(self.args("sync"))
        self.assertEqual(code, 0)
        self.assertEqual(self.env.read_text(), 'A=x\nB="hello world"\nC=\n')
        self.assertIn("Added 2 key(s)", out)
        self.assertEqual(parse_text(self.env.read_text()).as_dict()["B"], "hello world")
        self.assertEqual(run(self.args("check"))[0], 0)

    def test_sync_dry_run_does_not_write(self):
        self.env.write_text("A=x\n")
        self.example.write_text("A=\nB=1\n")
        code, out, _ = run(self.args("sync", "--dry-run"))
        self.assertEqual(code, 0)
        self.assertEqual(self.env.read_text(), "A=x\n")
        self.assertIn("B=1", out)

    def test_sync_creates_env_file(self):
        self.example.write_text("A=1\nB=2\n")
        code, _, _ = run(self.args("sync"))
        self.assertEqual(code, 0)
        self.assertEqual(self.env.read_text(), "A=1\nB=2\n")

    def test_sync_nothing_to_do(self):
        self.env.write_text("A=1\n")
        self.example.write_text("A=\n")
        code, out, _ = run(self.args("sync"))
        self.assertEqual(code, 0)
        self.assertIn("Nothing to sync", out)
        self.assertEqual(self.env.read_text(), "A=1\n")

    def test_sync_requires_example(self):
        code, _, err = run(self.args("sync"))
        self.assertEqual(code, 2)
        self.assertIn("file not found", err)

    def test_format_value_round_trips(self):
        for value in ["", "plain", "has space", 'q"uote', "back\\slash", "a#b", "it's", "x\ny", "t\tab"]:
            parsed = parse_text(f"K={format_value(value)}").as_dict()
            self.assertEqual(parsed["K"], value, msg=repr(value))

    def test_broken_pipe_is_not_an_error(self):
        from unittest import mock

        self.env.write_text("A=1\n")
        self.example.write_text("A=\n")
        with mock.patch("envmedic.cli._cmd_check", side_effect=BrokenPipeError):
            with mock.patch("os.dup2"), mock.patch("os.open", return_value=99):
                code = main(self.args("check"))
        self.assertEqual(code, 0)

    def test_no_command_is_usage_error(self):
        with self.assertRaises(SystemExit) as ctx:
            run([])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
