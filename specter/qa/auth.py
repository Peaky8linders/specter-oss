"""Optional API-key auth for the Specter Q&A endpoint.

Two tiers:

* **Privileged** — caller sends a valid ``X-Specter-Api-Key`` header that
  matches ``SPECTER_API_KEY`` env var. Higher rate-limit bucket; partner
  tag stamped on optional audit-chain hook.
* **Anonymous** — no header (or no configured key on this deploy).
  Lower rate-limit bucket keyed on the client IP hash.

Header present but invalid (typo / stale / wrong tenant) returns 403 —
silent downgrade to anonymous would mask consumer-side bugs. The dep
falls back to anonymous only when the deployment is unconfigured (no
``SPECTER_API_KEY`` set), so a stray header on a staged-but-inactive
deploy never blocks public traffic.
"""

from __future__ import annotations

import os
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

_specter_header = APIKeyHeader(name="X-Specter-Api-Key", auto_error=False)

_ENV_VAR = "SPECTER_API_KEY"


def _configured_key() -> str | None:
    """Read the configured partner key from env. None when unset."""
    val = os.environ.get(_ENV_VAR)
    if val is None:
        return None
    val = val.strip()
    return val or None


def validate_specter_api_key(api_key: str) -> bool:
    configured = _configured_key()
    if not configured:
        return False
    return secrets.compare_digest(api_key, configured)


async def require_specter_api_key(
    api_key: Annotated[str | None, Security(_specter_header)] = None,
) -> str:
    """Strict-auth dep — kept for back-compat / future privileged routes.

    Not used by the public Q&A route any more (the open-internet
    competition feature is anonymous-friendly via
    :func:`optional_specter_api_key`). Kept available so a future
    internal-only route can opt in to the fail-closed posture without
    re-implementing the validator.
    """
    if not _configured_key():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "specter_not_configured",
                "message": "Specter API integration is not configured on this deployment.",
            },
        )
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "specter_api_key_missing",
                "message": "Missing API key. Provide it via X-Specter-Api-Key.",
            },
        )
    if not validate_specter_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "specter_api_key_invalid",
                "message": "Invalid API key.",
            },
        )
    return api_key


async def optional_specter_api_key(
    api_key: Annotated[str | None, Security(_specter_header)] = None,
) -> str | None:
    """Optional-auth dep — returns the validated key or None.

    Powers the anonymous-friendly Specter EU AI Act Q&A endpoint
    (``POST /v1/eu-ai-act/ask``).

    Contract:
    - No header (key absent) → return ``None`` (anonymous tier).
    - Header present + matches configured key → return the key (privileged tier).
    - Header present but does NOT match → raise 403 (typo'd keys still fail loudly).
    - Deployment has no configured key (``_configured_key() is None``):
      header is ignored AND no 503 is raised — anonymous traffic flows
      regardless of partner-key provisioning. The route layer determines
      the tier from this dep's return value.

    The route layer combines this with two stacked rate-limit buckets
    (60/min for the privileged tier, 30/min per IP for anonymous) and
    distinct partner / anonymous tenant tags so a downstream observer
    can distinguish partner traffic from public traffic.
    """
    if not api_key:
        return None
    if not _configured_key():
        return None
    if not validate_specter_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "specter_api_key_invalid",
                "message": "Invalid API key.",
            },
        )
    return api_key


RequireSpecter = Depends(require_specter_api_key)
OptionalSpecter = Depends(optional_specter_api_key)
