# envmedic

Check your `.env` file against `.env.example` before it breaks your app.

`envmedic` is a small, zero-dependency command line tool that catches the classic
"works on my machine" configuration problems:

- **Missing keys** that are in `.env.example` but not in your `.env`
- **Duplicate keys** (later ones silently win)
- **Syntax errors** (unterminated quotes, malformed lines)
- **Extra keys** your example file doesn't document
- **Empty values** for keys that should be set

It exits with a non-zero code on problems, so it works in CI, pre-commit hooks and
deploy scripts.

## Install

```bash
pip install re4an-envmedic
```

Requires Python 3.9+. No third-party dependencies.

## Usage

### Check

```bash
envmedic check
```

```
Checking .env against .env.example

ERROR  missing from .env (2):
         - DATABASE_URL
         - SECRET_KEY
ERROR  duplicate keys in .env (1):
         - PORT (lines 3, 7)
WARN   not listed in .env.example (1):
         - OLD_FLAG

FAILED: 3 error(s), 1 warning(s)
```

| Option | Description |
| --- | --- |
| `--env PATH` | Env file to check (default `.env`) |
| `--example PATH` | Example file to compare against (default `.env.example`) |
| `--strict` | Also fail on warnings (extra and empty keys) |
| `--format json` | Machine-readable output |

### Sync

Append every key that is missing from your `.env`, using the values from `.env.example`:

```bash
envmedic sync --dry-run   # preview
envmedic sync             # write
```

Existing lines in your `.env` are never modified. If `.env` doesn't exist, it is created.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | No problems (warnings are allowed unless `--strict`) |
| `1` | Problems found |
| `2` | Usage error or file not found |

## Use it in CI

```yaml
- run: pip install re4an-envmedic
- run: envmedic check --env .env.ci --strict
```

## Supported syntax

```bash
KEY=value
export KEY=value
KEY="double quoted with \n escapes"
KEY='single quoted, literal'
KEY=value # inline comment
# full-line comment
```

Multi-line values are not supported.

## Development

```bash
git clone https://github.com/re4an/envmedic
cd envmedic
python -m pip install -e .
python -m unittest discover -s tests -v
```

## License

MIT
