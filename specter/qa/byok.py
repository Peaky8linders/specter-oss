"""BYOK (bring-your-own-key) helpers for per-request LLM provider selection.

Specter's primary deployment posture is "operator configures one server-
side env var (``MISTRAL_API_KEY`` / ``ANTHROPIC_API_KEY`` / ``OPENAI_API_KEY``)
and every request uses that retriever". The BYOK pattern is the second
posture: a tenant supplies *their own* provider + key on every request,
the server uses it for that one call, and the key is never persisted.

The webapp ships a settings drawer that stores the user's chosen provider
+ key in ``localStorage`` and forwards them as two headers:

* ``X-Specter-LLM-Provider`` — one of ``claude`` / ``openai``.
  Case-insensitive. Anything else is rejected.
* ``X-Specter-LLM-Key`` — the user's API key. Bearer-style. Capped at 2K
  characters defensively.

Header parsing rules:

* Both headers must be present. Either one alone is rejected (a key
  without a provider is ambiguous; a provider without a key is the
  default server-side path).
* Provider names are normalised (lowercased + trimmed). Empty or
  unrecognised values fall through to "no BYOK" so the server-side
  default retriever fires.
* The key is only used to construct the per-request retriever — it is
  never logged, never persisted, never echoed back to the client.

Why a header pair instead of one combined ``Authorization: Bearer``?

* The Q&A route already uses ``X-Specter-Api-Key`` for the rate-limit
  tier toggle. Reusing ``Authorization`` would conflict with reverse
  proxies that attach their own.
* Two-header form makes the provider explicit on the wire — useful for
  audit logs and for the operator to grep-count BYOK traffic by
  provider without a body parse.

Hallucination guard remains downstream: the per-request retriever
returns the same ``RetrieverResponse`` shape as the server-side default,
and the route's ``reference_from_article_ref`` strips hallucinated
citations regardless of which provider produced them.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import Request

from specter.api.qa_route import RetrieverFn

logger = logging.getLogger(__name__)


# Header names. We pin them as constants so a future audit-logging hook
# can grep them out of an incoming request without re-deriving the
# string. ``X-Specter-LLM-Key`` deliberately echoes ``X-Specter-Api-Key``
# (the rate-limit tier header) so a operator running a tcpdump on the
# wire only sees one prefix.
HEADER_PROVIDER = "X-Specter-LLM-Provider"
HEADER_KEY = "X-Specter-LLM-Key"

# Cap defensive: the longest currently-issued provider key (OpenAI sk-)
# is ~165 chars. 2 KiB allows for a future provider format without
# letting a malicious client paste an attack string.
_MAX_KEY_LEN = 2048


ProviderName = Literal["claude", "openai"]
_VALID_PROVIDERS: frozenset[str] = frozenset({"mistral", "claude", "openai"})


def parse_byok_headers(request: Request) -> tuple[ProviderName | None, str | None]:
    """Pull the BYOK provider + key out of the request headers.

    Returns ``(provider, key)`` where:

    * Both are ``None`` when no BYOK headers are present (or are malformed).
      The caller should fall through to the server-side default retriever.
    * Both are populated when a valid pair is on the request. The caller
      should construct a per-request retriever for this provider + key.
    """
    provider_raw = request.headers.get(HEADER_PROVIDER, "").strip().lower()
    key_raw = request.headers.get(HEADER_KEY, "").strip()

    if not provider_raw or not key_raw:
        return None, None

    if provider_raw not in _VALID_PROVIDERS:
        logger.debug(
            "byok.unrecognised_provider header=%s len=%d",
            HEADER_PROVIDER, len(provider_raw),
        )
        return None, None

    if len(key_raw) > _MAX_KEY_LEN:
        logger.warning(
            "byok.oversized_key provider=%s len=%d cap=%d",
            provider_raw, len(key_raw), _MAX_KEY_LEN,
        )
        return None, None

    return provider_raw, key_raw  # type: ignore[return-value]


def build_byok_retriever(provider: ProviderName, api_key: str) -> RetrieverFn | None:
    """Construct a one-off retriever bound to ``api_key`` for ``provider``.

    Returns ``None`` when the requested provider's SDK is not installed
    on this deploy — caller should fall through to the server-side
    default. We import the retriever factories lazily so this module
    stays cheap to import on a deploy that ships only one of the three.
    """
    try:
        if provider == "mistral":
            from specter.qa.mistral_retriever import make_mistral_retriever

            return make_mistral_retriever(api_key=api_key)
        if provider == "claude":
            from specter.qa.claude_retriever import make_claude_retriever

            return make_claude_retriever(api_key=api_key)
        if provider == "openai":
            from specter.qa.openai_retriever import make_openai_retriever

            return make_openai_retriever(api_key=api_key)
    except Exception as exc:  # noqa: BLE001 — soft-fail on missing SDK
        logger.warning(
            "byok.retriever_init_failed provider=%s error=%s",
            provider, str(exc)[:200],
        )
        return None

    return None


def resolve_request_retriever(
    request: Request,
    *,
    default: RetrieverFn,
) -> RetrieverFn:
    """Return the retriever to use for this request — BYOK or default.

    When the request carries valid BYOK headers and the requested
    provider's SDK is installed, returns a fresh per-request retriever.
    Otherwise returns ``default`` (the server-side, env-var-configured
    retriever the route was built with).
    """
    provider, api_key = parse_byok_headers(request)
    if provider is None or api_key is None:
        return default

    byok = build_byok_retriever(provider, api_key)
    if byok is None:
        # Provider asked for but SDK missing: log + degrade to default
        # rather than 503ing. The default is at worst the closed-world
        # refusal stub, which is still a structured response.
        logger.info(
            "byok.fallthrough_to_default provider=%s (sdk likely missing)",
            provider,
        )
        return default
    return byok


__all__ = [
    "HEADER_KEY",
    "HEADER_PROVIDER",
    "ProviderName",
    "build_byok_retriever",
    "parse_byok_headers",
    "resolve_request_retriever",
]
