"""Loader for the vendored OWASP APTS requirements catalog.

Reads ``data/apts_requirements.json`` (CC BY-SA 4.0, OWASP Foundation 2026)
into typed ``APTSRequirement`` records and exposes the standard accessor
patterns: by-id lookup, per-domain index, per-tier index, and the eight
canonical domain labels. The cache is process-lifetime; the file is
immutable in-process and a refresh requires a redeploy.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from specter.apts.models import APTSDomain, APTSRequirement, APTSTier

_DATA_DIR = Path(__file__).resolve().parent / "data"
_REQUIREMENTS_PATH = _DATA_DIR / "apts_requirements.json"

# Pinned upstream version. Bumped when ``scripts/_refresh_apts_standard.py``
# re-fetches the catalog and the test fixtures are reconciled.
APTS_VERSION = "0.1.0"


@lru_cache(maxsize=1)
def _raw_payload() -> dict:
    return json.loads(_REQUIREMENTS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_requirements() -> tuple[APTSRequirement, ...]:
    """Return all 173 requirements in upstream order."""
    payload = _raw_payload()
    raw = payload.get("requirements", [])
    return tuple(APTSRequirement.model_validate(row) for row in raw)


@lru_cache(maxsize=1)
def _id_index() -> dict[str, APTSRequirement]:
    return {r.id: r for r in load_requirements()}


def requirement_by_id(requirement_id: str) -> APTSRequirement | None:
    """Look up a single requirement by ``APTS-XX-NNN`` id; ``None`` on miss."""
    return _id_index().get(requirement_id)


def requirements_by_domain(domain: APTSDomain) -> tuple[APTSRequirement, ...]:
    """All requirements in a single domain, upstream order."""
    return tuple(r for r in load_requirements() if r.domain == domain)


def requirements_by_tier(tier: APTSTier) -> tuple[APTSRequirement, ...]:
    """All requirements at a specific tier, upstream order."""
    return tuple(r for r in load_requirements() if r.tier == tier)


def list_domains() -> tuple[APTSDomain, ...]:
    """Return the eight canonical domains in upstream order."""
    return tuple(APTSDomain)


def manifest() -> dict:
    """Return version + source metadata for the vendored catalog."""
    payload = _raw_payload()
    return {
        "version": payload.get("version", APTS_VERSION),
        "source": payload.get("source", "OWASP Autonomous Penetration Testing Standard"),
        "last_updated": payload.get("last_updated"),
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "upstream_url": "https://github.com/OWASP/APTS",
        "requirement_count": len(load_requirements()),
    }
