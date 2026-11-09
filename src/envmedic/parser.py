"""A small, strict parser for dotenv-style files.

Supported syntax:
    KEY=value
    export KEY=value
    KEY="double quoted, supports \\n \\t \\r \\" \\\\ escapes"
    KEY='single quoted, taken literally'
    KEY=value # inline comment (whitespace before '#' required)
    # full-line comments and blank lines

Multi-line values are not supported.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_LINE_RE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
_INLINE_COMMENT_RE = re.compile(r"\s+#")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


@dataclass(frozen=True)
class Entry:
    key: str
    value: str
    line: int


@dataclass(frozen=True)
class SyntaxIssue:
    line: int
    message: str


@dataclass
class ParseResult:
    entries: List[Entry] = field(default_factory=list)
    issues: List[SyntaxIssue] = field(default_factory=list)

    def as_dict(self) -> Dict[str, str]:
        """Map of key -> value. If a key repeats, the last one wins."""
        return {e.key: e.value for e in self.entries}


def _parse_quoted(rest: str) -> Optional[Tuple[str, str]]:
    """Parse a quoted value. `rest` starts with the opening quote.

    Returns (value, remainder_after_closing_quote), or None if unterminated.
    """
    quote = rest[0]
    out: List[str] = []
    i = 1
    while i < len(rest):
        ch = rest[i]
        if quote == '"' and ch == "\\" and i + 1 < len(rest):
            nxt = rest[i + 1]
            out.append(_ESCAPES.get(nxt, "\\" + nxt))
            i += 2
            continue
        if ch == quote:
            return "".join(out), rest[i + 1 :]
        out.append(ch)
        i += 1
    return None


def parse_text(text: str) -> ParseResult:
    result = ParseResult()
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = _LINE_RE.match(line)
        if not match:
            result.issues.append(
                SyntaxIssue(number, "invalid line (expected KEY=VALUE)")
            )
            continue

        key, raw_value = match.group(1), match.group(2).strip()

        if raw_value[:1] in ('"', "'"):
            parsed = _parse_quoted(raw_value)
            if parsed is None:
                result.issues.append(
                    SyntaxIssue(number, f"unterminated quoted value for {key}")
                )
                continue
            value, remainder = parsed
            remainder = remainder.strip()
            if remainder and not remainder.startswith("#"):
                result.issues.append(
                    SyntaxIssue(number, f"unexpected text after closing quote for {key}")
                )
                continue
        elif raw_value.startswith("#"):
            value = ""
        else:
            value = _INLINE_COMMENT_RE.split(raw_value, maxsplit=1)[0].strip()

        result.entries.append(Entry(key, value, number))
    return result


def parse_file(path: Path) -> ParseResult:
    # utf-8-sig transparently strips a BOM if present.
    return parse_text(Path(path).read_text(encoding="utf-8-sig"))
