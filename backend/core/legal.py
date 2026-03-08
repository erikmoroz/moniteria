"""Reads and caches legal documents (Privacy Policy, Terms of Service) from docs/legal/."""

from functools import lru_cache
from pathlib import Path

LEGAL_DIR = Path(__file__).resolve().parent.parent.parent / 'docs' / 'legal'


def _parse(filename: str) -> dict:
    """Read a markdown file, strip YAML frontmatter, return meta + content."""
    text = (LEGAL_DIR / filename).read_text(encoding='utf-8')

    if not text.startswith('---\n'):
        return {'version': '1.0', 'effective_date': '', 'content': text}

    try:
        end = text.index('\n---\n', 4)
    except ValueError:
        return {'version': '1.0', 'effective_date': '', 'content': text}

    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ':' in line:
            key, _, value = line.partition(':')
            meta[key.strip()] = value.strip().strip('"\'')

    return {
        'version': meta.get('version', '1.0'),
        'effective_date': meta.get('effective_date', ''),
        'content': text[end + 5 :].strip(),
    }


@lru_cache(maxsize=None)
def get_terms() -> dict:
    """Return parsed Terms of Service (cached after first read)."""
    return _parse('terms-of-service.md')


@lru_cache(maxsize=None)
def get_privacy() -> dict:
    """Return parsed Privacy Policy (cached after first read)."""
    return _parse('privacy-policy.md')
