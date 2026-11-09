"""Compare a parsed .env file against a parsed .env.example file."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from envmedic.parser import ParseResult


@dataclass
class SyntaxProblem:
    file: str
    line: int
    message: str


@dataclass
class Report:
    env_file: str
    example_file: str
    missing: List[str] = field(default_factory=list)
    extra: List[str] = field(default_factory=list)
    empty: List[str] = field(default_factory=list)
    duplicates: Dict[str, List[int]] = field(default_factory=dict)
    syntax: List[SyntaxProblem] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.missing) + len(self.duplicates) + len(self.syntax)

    @property
    def warning_count(self) -> int:
        return len(self.extra) + len(self.empty)

    def has_problems(self, strict: bool = False) -> bool:
        """Errors always fail. Warnings fail only in strict mode."""
        if self.error_count:
            return True
        return strict and self.warning_count > 0

    def as_dict(self, strict: bool = False) -> Dict[str, Any]:
        data = asdict(self)
        data["errors"] = self.error_count
        data["warnings"] = self.warning_count
        data["ok"] = not self.has_problems(strict)
        return data


def _unique(items: List[str]) -> List[str]:
    seen = set()
    ordered = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def check(
    env: ParseResult,
    example: ParseResult,
    env_label: str = ".env",
    example_label: str = ".env.example",
) -> Report:
    env_map = env.as_dict()
    example_map = example.as_dict()
    env_keys = _unique([e.key for e in env.entries])
    example_keys = _unique([e.key for e in example.entries])

    lines_by_key: Dict[str, List[int]] = {}
    for entry in env.entries:
        lines_by_key.setdefault(entry.key, []).append(entry.line)

    report = Report(env_file=env_label, example_file=example_label)
    report.missing = [k for k in example_keys if k not in env_map]
    report.extra = [k for k in env_keys if k not in example_map]
    report.empty = [k for k in env_keys if k in example_map and env_map[k] == ""]
    report.duplicates = {k: v for k, v in lines_by_key.items() if len(v) > 1}
    report.syntax = [
        SyntaxProblem(env_label, i.line, i.message) for i in env.issues
    ] + [SyntaxProblem(example_label, i.line, i.message) for i in example.issues]
    return report
