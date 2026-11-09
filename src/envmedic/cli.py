"""Command line interface for envmedic."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

from envmedic import __version__
from envmedic.checker import Report, check
from envmedic.parser import ParseResult, parse_file

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_USAGE = 2


def render_text(report: Report, strict: bool = False) -> str:
    out: List[str] = [f"Checking {report.env_file} against {report.example_file}", ""]

    for problem in report.syntax:
        out.append(f"ERROR  {problem.file}:{problem.line}: {problem.message}")
    if report.missing:
        out.append(f"ERROR  missing from {report.env_file} ({len(report.missing)}):")
        out.extend(f"         - {key}" for key in report.missing)
    if report.duplicates:
        out.append(f"ERROR  duplicate keys in {report.env_file} ({len(report.duplicates)}):")
        for key, lines in report.duplicates.items():
            where = ", ".join(str(n) for n in lines)
            out.append(f"         - {key} (lines {where})")
    if report.extra:
        out.append(
            f"WARN   not listed in {report.example_file} ({len(report.extra)}):"
        )
        out.extend(f"         - {key}" for key in report.extra)
    if report.empty:
        out.append(f"WARN   empty values in {report.env_file} ({len(report.empty)}):")
        out.extend(f"         - {key}" for key in report.empty)

    if report.error_count or report.warning_count:
        out.append("")

    status = "FAILED" if report.has_problems(strict) else "OK"
    summary = f"{status}: {report.error_count} error(s), {report.warning_count} warning(s)"
    if strict:
        summary += " [strict]"
    out.append(summary)
    return "\n".join(out)


def format_value(value: str) -> str:
    """Format a value so that the parser reads back exactly the same string."""
    if value == "":
        return ""
    if re.search(r"[\s#\"'\\]", value):
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\t", "\\t")
            .replace("\r", "\\r")
        )
        return f'"{escaped}"'
    return value


def _require_file(path: Path) -> bool:
    if not path.is_file():
        print(f"envmedic: error: file not found: {path}", file=sys.stderr)
        return False
    return True


def _cmd_check(args: argparse.Namespace) -> int:
    env_path, example_path = Path(args.env), Path(args.example)
    if not (_require_file(env_path) and _require_file(example_path)):
        return EXIT_USAGE

    report = check(
        parse_file(env_path),
        parse_file(example_path),
        env_label=str(args.env),
        example_label=str(args.example),
    )
    if args.format == "json":
        print(json.dumps(report.as_dict(args.strict), indent=2))
    else:
        print(render_text(report, args.strict))
    return EXIT_PROBLEMS if report.has_problems(args.strict) else EXIT_OK


def _cmd_sync(args: argparse.Namespace) -> int:
    env_path, example_path = Path(args.env), Path(args.example)
    if not _require_file(example_path):
        return EXIT_USAGE

    example = parse_file(example_path)
    env = parse_file(env_path) if env_path.is_file() else ParseResult()

    for issue in example.issues:
        print(
            f"envmedic: warning: {example_path}:{issue.line}: {issue.message} (skipped)",
            file=sys.stderr,
        )

    env_keys = set(env.as_dict())
    example_map = example.as_dict()
    missing: List[str] = []
    for entry in example.entries:
        if entry.key not in env_keys and entry.key not in missing:
            missing.append(entry.key)

    if not missing:
        print(f"Nothing to sync: {env_path} already has every key.")
        return EXIT_OK

    new_lines = [f"{key}={format_value(example_map[key])}" for key in missing]

    if args.dry_run:
        print(f"Would add {len(missing)} key(s) to {env_path}:")
        for line in new_lines:
            print(f"  {line}")
        return EXIT_OK

    prefix = ""
    if env_path.is_file() and env_path.stat().st_size > 0:
        with open(env_path, "rb") as fh:
            fh.seek(-1, os.SEEK_END)
            if fh.read(1) != b"\n":
                prefix = "\n"
    with open(env_path, "a", encoding="utf-8", newline="") as fh:
        fh.write(prefix + "\n".join(new_lines) + "\n")

    print(f"Added {len(missing)} key(s) to {env_path}: {', '.join(missing)}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="envmedic",
        description="Check your .env file against .env.example.",
    )
    parser.add_argument("--version", action="version", version=f"envmedic {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_paths(p: argparse.ArgumentParser) -> None:
        p.add_argument("--env", default=".env", help="path to your env file (default: .env)")
        p.add_argument(
            "--example",
            default=".env.example",
            help="path to the example file (default: .env.example)",
        )

    check_p = sub.add_parser("check", help="report missing, extra, empty and duplicate keys")
    add_paths(check_p)
    check_p.add_argument(
        "--strict", action="store_true", help="treat warnings (extra/empty keys) as failures"
    )
    check_p.add_argument("--format", choices=["text", "json"], default="text")
    check_p.set_defaults(func=_cmd_check)

    sync_p = sub.add_parser("sync", help="append keys missing from your env file")
    add_paths(sync_p)
    sync_p.add_argument(
        "--dry-run", action="store_true", help="show what would be added without writing"
    )
    sync_p.set_defaults(func=_cmd_sync)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:
        # Output was piped to something that closed early (e.g. `| head`).
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except (OSError, ValueError):
            pass
        return EXIT_OK
    except (OSError, UnicodeDecodeError) as exc:
        print(f"envmedic: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
