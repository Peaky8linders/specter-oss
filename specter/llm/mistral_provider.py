"""Shared, typed Mistral La Plateforme provider for Specter.

One process-wide client, one retry policy, one structured-log envelope.
Used by:

* :mod:`specter.qa.mistral_retriever` — Mistral-backed retriever for
  the public Q&A endpoint at :func:`specter.api.qa_route.make_qa_router`.

Hosts that wire a different LLM (Anthropic, OpenAI, on-prem) ship a
custom retriever via the pluggable protocol; this provider is the
reference implementation so that one env var (``MISTRAL_API_KEY``)
unlocks a working grounded Q&A surface.

Design rules:

1. Lazy-init the SDK on first ``complete()`` so importing this module
   never raises if neither ``MISTRAL_API_KEY`` nor ``api_key=...`` is
   set. Hosts on a non-Mistral deploy can still ``import specter.llm``.
2. Read the key from ``os.environ`` directly (NOT a pydantic-settings
   field). An explicit ``api_key=...`` to ``MistralProvider`` always
   wins over the env var. Re-reading from ``os.environ`` per-call
   matches the operator-friendly pattern: an env-var rebind on the
   deploy target takes effect on the next request, not the next deploy.
3. NEVER raise from ``complete()`` — return a :class:`MistralResponse`
   with ``error`` populated. Callers always have a fallback path
   (closed-world refusal in the QA retriever, deterministic answer in
   the rule-based judge); they need a value to fall through, not an
   exception to swallow.
4. Retry once on transient (HTTP 429 / 5xx / network blip) with a 1.5s
   backoff. Do NOT retry on 4xx auth — that is a config error and a
   retry storm just hides it.
5. Every call emits a structured log line (``mistral_provider.call``)
   with input_chars / output_chars / latency_ms / model / finish_reason.

Out of scope (deliberately):

* Streaming responses — the Q&A endpoint is request/response.
* Tool calling — add it the day a feature actually needs it.
* Async API — the provider is sync; async callers wrap it in a thread
  executor.
"""

from __future__ import annotations

import logging
import os
import time
from threading import Lock
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Retryable HTTP status codes (rate limit + transient backend).
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Single-retry backoff seed. Bounded so a stuck provider can't pin a
# request thread for >2s; the caller has a fallback on error anyway.
_BACKOFF_S = 1.5
_TIMEOUT_S = 30.0

_ENV_VAR = "MISTRAL_API_KEY"


class MistralRequest(BaseModel):
    """Typed request envelope for :meth:`MistralProvider.complete`."""

    system: str = Field(description="System prompt.")
    user: str = Field(description="User message.")
    model: str = Field(
        default="mistral-large-latest",
        description=(
            "Mistral model id. Defaults to ``mistral-large-latest``; "
            "callers can pin a smaller/cheaper model "
            "(``mistral-small-latest``) per feature."
        ),
    )
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    response_format: Literal["text", "json_object"] = Field(default="text")


class MistralResponse(BaseModel):
    """Typed response envelope. Never raises; ``error`` is populated on failure."""

    text: str = Field(default="", description="Assistant reply text.")
    model: str = Field(default="", description="Model id Mistral served.")
    finish_reason: str = Field(default="", description="Mistral stop reason.")
    usage_input_tokens: int = Field(default=0, ge=0)
    usage_output_tokens: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    error: str | None = Field(
        default=None,
        description=(
            "None on success. Populated on auth/transport/parse failure so "
            "callers can branch to their fallback path without a try/except."
        ),
    )


def is_mistral_enabled(api_key: str | None = None) -> bool:
    """``True`` iff a Mistral API key is available.

    Args:
      api_key: explicit key to check. When ``None``, falls back to
        the ``MISTRAL_API_KEY`` env var.

    Callers MUST gate their Mistral branch on this check. The provider
    is fail-soft (returns a response with ``error`` set when the key is
    missing) but skipping the call entirely is faster than catching the
    soft failure.
    """
    if api_key:
        return True
    return bool(os.environ.get(_ENV_VAR))


# ─── Provider-toggle resolution ─────────────────────────────────────────
#
# Every LLM-touching feature carries a per-feature toggle env var. The
# operator can set the toggle to one of two explicit literals:
#
#   ``mistral`` — force Mistral (provider must reject if key missing)
#   ``stub``    — force the no-op stub retriever (closed-world refusal)
#
# When the toggle is unset, empty, or the explicit ``auto`` literal we
# pick Mistral if a key is available, else fall back to ``stub``.
ResolvedProvider = Literal["mistral", "stub"]
ProviderName = Literal["mistral", "stub", "auto"]


def resolve_provider(
    env_value: str | None,
    *,
    default_when_auto: ResolvedProvider = "stub",
    api_key: str | None = None,
) -> ResolvedProvider:
    """Convert a toggle env var into the actual provider that will fire.

    - ``"mistral"`` / ``"stub"`` (any case, with surrounding whitespace)
      — honoured verbatim.
    - ``"auto"`` / ``None`` / empty / unrecognised — return ``"mistral"``
      when a key is available (kwarg or ``MISTRAL_API_KEY``),
      else ``default_when_auto``.

    Unknown / typo'd values intentionally fall through to the auto-pick
    branch rather than raising. The QA retriever has its own fallback
    on Mistral failure (closed-world refusal) so a typo just lands on
    the safe default.
    """
    if env_value is None:
        candidate = ""
    else:
        candidate = env_value.strip().lower()

    if candidate == "mistral":
        return "mistral"
    if candidate == "stub":
        return "stub"

    if is_mistral_enabled(api_key=api_key):
        return "mistral"
    return default_when_auto


# Singleton state. We hold a single SDK client across the process so the
# underlying httpx connection pool is reused. ``_lock`` guards lazy init
# under FastAPI's threadpool — multiple incoming requests can race the
# very first ``get_mistral_provider()``.
_provider_singleton: MistralProvider | None = None
_provider_lock = Lock()


def get_mistral_provider(api_key: str | None = None) -> MistralProvider:
    """Process-wide singleton :class:`MistralProvider`.

    Args:
      api_key: optional key override. When provided, ALWAYS builds a
        new provider — singleton is bypassed so different callers can
        run with different keys (e.g. multi-tenant). When ``None``,
        returns the cached singleton (which reads ``MISTRAL_API_KEY``
        from env on first ``complete()``).

    Lazy-init on first call. The SDK client itself is also lazy inside
    :class:`MistralProvider` so importing the module on a non-Mistral
    deploy has no side effects.
    """
    if api_key is not None:
        return MistralProvider(api_key=api_key)
    global _provider_singleton
    if _provider_singleton is None:
        with _provider_lock:
            if _provider_singleton is None:
                _provider_singleton = MistralProvider()
    return _provider_singleton


def reset_mistral_provider() -> None:
    """Test seam: drop the singleton so ``monkeypatch.setenv`` takes effect."""
    global _provider_singleton
    with _provider_lock:
        _provider_singleton = None


class MistralProvider:
    """Synchronous one-shot completion against Mistral La Plateforme.

    Construct via :func:`get_mistral_provider` (singleton) or directly
    with an explicit ``api_key`` for non-shared use. For tests, pass
    a stub ``client`` to avoid hitting the SDK. :meth:`complete` NEVER
    raises — failures land in :attr:`MistralResponse.error`.

    Example::

        # Use env var (default)
        provider = MistralProvider()

        # Or pass key explicitly (overrides env)
        provider = MistralProvider(api_key="my-key-...")

        res = provider.complete(MistralRequest(
            system="Cite only EU AI Act articles you can verify.",
            user="What does Art. 15 require for high-risk systems?",
        ))
        if res.error:
            ...  # fallback path
        else:
            print(res.text)
    """

    def __init__(
        self,
        *,
        client: Any | None = None,
        api_key: str | None = None,
    ) -> None:
        """Construct the provider.

        Args:
          client: test seam — pass a pre-built client to avoid real HTTP.
            In production we lazy-init in :meth:`_ensure_client` so
            importing the module on a deploy without ``MISTRAL_API_KEY``
            is side-effect free.
          api_key: optional explicit key. When provided, this OVERRIDES
            the ``MISTRAL_API_KEY`` env var. Useful for:

            * passing the key in test fixtures
            * multi-tenant deployments where the key is per-request
            * library users who don't want to use env vars

            When ``None`` (the default), the provider reads
            ``MISTRAL_API_KEY`` from ``os.environ`` on every call.
        """
        # Test seam: callers can inject a pre-built client (no real HTTP).
        self._client: Any | None = client
        self._client_init_attempted: bool = client is not None
        # Explicit key wins over the env var when set. Stored for the
        # lifetime of the provider — re-instantiate to rotate.
        self._explicit_api_key: str | None = api_key

    def _ensure_client(self) -> tuple[Any | None, str | None]:
        """Build the SDK client on demand. Returns ``(client, error)``.

        Resolution order for the API key:

        1. ``api_key=`` argument passed to :meth:`__init__` (if any)
        2. ``MISTRAL_API_KEY`` env var (re-read every call so a Railway
           env-var rebind takes effect on the next request, not the
           next deploy)

        The env-var fallback re-reads from ``os.environ`` every call
        because pydantic-settings snapshots env at instantiation time
        and a deploy-target rebind would otherwise require a process
        restart for the cached settings to see the new key.
        """
        if self._client is not None:
            return self._client, None

        api_key = self._explicit_api_key or os.environ.get(_ENV_VAR)
        if not api_key:
            return None, f"{_ENV_VAR} is not set and no api_key was passed"

        try:
            # Lazy import: lets unit tests run without the SDK installed
            # by injecting a stub client at construction time.
            # The SDK exports the client at ``mistralai.client.Mistral``
            # in 1.x — top-level import is unstable across versions.
            from mistralai.client import Mistral  # type: ignore[import-not-found]
        except ImportError:
            try:
                from mistralai import Mistral  # type: ignore[import-not-found]  # noqa: F401
            except ImportError as exc:
                return None, f"mistralai SDK not installed: {exc}"

        try:
            self._client = Mistral(api_key=api_key)
        except Exception as exc:  # noqa: BLE001 — soft-fail per design rule 3
            logger.warning(
                "mistral_provider.client_init_failed error=%s",
                str(exc)[:200],
            )
            return None, f"Mistral client init failed: {str(exc)[:200]}"

        self._client_init_attempted = True
        return self._client, None

    def complete(self, req: MistralRequest) -> MistralResponse:
        """One-shot synchronous completion. Never raises.

        Retry policy: one extra attempt on 429/5xx with a 1.5s backoff.
        4xx auth errors fail-fast (returning a response with ``error``).
        """
        client, init_err = self._ensure_client()
        if client is None or init_err is not None:
            return MistralResponse(
                model=req.model,
                error=init_err or "Mistral client unavailable",
            )

        kwargs: dict[str, Any] = {
            "model": req.model,
            "messages": [
                {"role": "system", "content": req.system},
                {"role": "user", "content": req.user},
            ],
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
        }
        if req.response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        attempts = 2  # initial + one retry on transient
        last_err: str | None = None
        for attempt in range(attempts):
            t0 = time.monotonic()
            try:
                # Sync path; SDK exposes ``complete`` (sync) and
                # ``complete_async``. We use the sync variant so callers
                # don't have to spin an event loop.
                response = client.chat.complete(**kwargs)
                latency_ms = int((time.monotonic() - t0) * 1000)
                if not getattr(response, "choices", None):
                    last_err = "Mistral returned no choices"
                    logger.warning(
                        "mistral_provider.empty_response model=%s latency_ms=%d",
                        req.model, latency_ms,
                    )
                    # Treat as transient — empty choices have been observed
                    # under provider load. One retry, then give up.
                    if attempt + 1 < attempts:
                        time.sleep(_BACKOFF_S)
                        continue
                    return MistralResponse(
                        model=req.model, latency_ms=latency_ms,
                        error=last_err,
                    )

                choice = response.choices[0]
                content = getattr(choice.message, "content", None) or ""
                finish_reason = getattr(choice, "finish_reason", "") or ""
                usage = getattr(response, "usage", None)
                in_tok = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
                out_tok = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0

                logger.info(
                    "mistral_provider.call model=%s finish=%s in_chars=%d "
                    "out_chars=%d latency_ms=%d in_tok=%d out_tok=%d",
                    req.model, finish_reason,
                    len(req.system) + len(req.user), len(content),
                    latency_ms, in_tok, out_tok,
                )
                return MistralResponse(
                    text=content,
                    model=req.model,
                    finish_reason=finish_reason,
                    usage_input_tokens=in_tok,
                    usage_output_tokens=out_tok,
                    latency_ms=latency_ms,
                )
            except Exception as exc:  # noqa: BLE001 — soft-fail per design rule 3
                latency_ms = int((time.monotonic() - t0) * 1000)
                status_code = _extract_status_code(exc)
                last_err = f"{type(exc).__name__}: {str(exc)[:200]}"
                retryable = (
                    status_code is not None and status_code in _RETRYABLE_STATUS
                ) or status_code is None and _looks_like_network_error(exc)
                logger.warning(
                    "mistral_call_failed model=%s error=%s status=%s "
                    "attempt=%d retryable=%s latency_ms=%d",
                    req.model, str(exc)[:200], status_code,
                    attempt + 1, retryable, latency_ms,
                )
                if not retryable or attempt + 1 >= attempts:
                    return MistralResponse(
                        model=req.model, latency_ms=latency_ms,
                        error=last_err,
                    )
                time.sleep(_BACKOFF_S)
                continue

        # Defensive — the loop returns on every path. Belt for mypy.
        return MistralResponse(model=req.model, error=last_err or "unknown error")


def _extract_status_code(exc: Exception) -> int | None:
    """Pull an HTTP status code out of a Mistral SDK exception if present."""
    raw = getattr(exc, "raw_response", None)
    if raw is None:
        return None
    code = getattr(raw, "status_code", None)
    if code is None:
        return None
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


def _looks_like_network_error(exc: Exception) -> bool:
    """Best-effort: should we retry an exception with no status code?"""
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    name = type(exc).__name__
    return name in {
        "ConnectError",
        "ReadTimeout",
        "ConnectTimeout",
        "WriteTimeout",
        "RemoteProtocolError",
        "NetworkError",
    }
