"""Reads and caches legal documents (Privacy Policy, Terms of Service) from docs/legal/."""

from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.template import Context, Template

LEGAL_DIR = Path(__file__).resolve().parent.parent.parent / 'docs' / 'legal'


def _get_legal_context() -> dict:
    """Build template context from Django settings."""
    return {
        'operator_name': settings.LEGAL_OPERATOR_NAME,
        'operator_type': settings.LEGAL_OPERATOR_TYPE,
        'contact_email': settings.LEGAL_CONTACT_EMAIL,
        'contact_address': settings.LEGAL_CONTACT_ADDRESS,
        'jurisdiction': settings.LEGAL_JURISDICTION,
        'is_individual': settings.LEGAL_OPERATOR_TYPE == 'individual',
        'is_company': settings.LEGAL_OPERATOR_TYPE == 'company',
    }


def _parse(filename: str) -> dict:
    """Read a markdown file, strip YAML frontmatter, render template variables, return meta + content."""
    text = (LEGAL_DIR / filename).read_text(encoding='utf-8')

    if not text.startswith('---\n'):
        content = Template(text).render(Context(_get_legal_context()))
        return {'version': '1.0', 'effective_date': '', 'content': content}

    try:
        end = text.index('\n---\n', 4)
    except ValueError:
        content = Template(text).render(Context(_get_legal_context()))
        return {'version': '1.0', 'effective_date': '', 'content': content}

    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ':' in line:
            key, _, value = line.partition(':')
            meta[key.strip()] = value.strip().strip('"\'')

    raw_content = text[end + 5 :].strip()
    content = Template(raw_content).render(Context(_get_legal_context()))

    return {
        'version': meta.get('version', '1.0'),
        'effective_date': meta.get('effective_date', ''),
        'content': content,
    }


@lru_cache(maxsize=None)
def get_terms() -> dict:
    """Return parsed Terms of Service (cached after first read)."""
    return _parse('terms-of-service.md')


@lru_cache(maxsize=None)
def get_privacy() -> dict:
    """Return parsed Privacy Policy (cached after first read)."""
    return _parse('privacy-policy.md')
