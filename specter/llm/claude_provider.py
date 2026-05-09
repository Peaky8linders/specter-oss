"""Shared, typed Anthropic Claude provider for Specter.

Mirrors the design contract of :mod:`specter.llm.mistral_provider`:
one process-wide client, one retry policy, one structured-log envelope,
fail-soft completion (never raises). Used by:

* :mod:`specter.qa.claude_retriever` — Claude-backed retriever for the
  public Q&A endpoint at :func:`specter.api.qa_route.make_qa_router`.

Why a second provider?
^^^^^^^^^^^^^^^^^^^^^^
The Mistral retriever is the reference implementation for the Q&A
surface. Hosts that prefer Claude (or whose tenants pay for Claude
seats) wire this provider — same fail-soft contract, same closed-world
refusal posture, same hallucination guard at the route layer. The
provider itself does not know about EU AI Act citations; that is the
retriever's job.

Design rules (kept in lockstep with mistral_provider):

1. Lazy-init the SDK on first ``complete()``. Importing this module
   never raises if neither ``ANTHROPIC_API_KEY`` nor ``api_key=...`` is
   set; hosts on a non-Claude deploy can still ``import specter.llm``.
2. Read the key from ``os.environ`` directly — explicit ``api_key=``
   wins over the env var. Re-reading per-call matches the operator-
   friendly pattern: an env-var rebind on the deploy target takes
   effect on the next request, not the next deploy.
3. NEVER raise from ``complete()`` — return a :class:`ClaudeResponse`
   with ``error`` populated. Callers always have a fallback (closed-
   world refusal in the QA retriever).
4. Retry once on transient (HTTP 429 / 5xx / network blip) with a 1.5s
   backoff. Do NOT retry on 4xx auth — that is a config error and a
   retry storm just hides it.
5. Every call emits a structured log line (``claude_provider.call``)
   with input_chars / output_chars / latency_ms / model / stop_reason.

Out of scope (deliberately):

* Streaming responses — the Q&A endpoint is request/response.
* Tool calling — add the day a feature actually needs it.
* Async API — sync only; async callers wrap in a thread executor.
"""

from __future__ import annotations

import logging
import os
import time
from threading import Lock
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_BACKOFF_S = 1.5
_TIMEOUT_S = 30.0

_ENV_VAR = "ANTHROPIC_API_KEY"

# Default model: Claude is shipped on a fast-moving release cadence;
# pin the most-capable current model and let callers override per-feature.
_DEFAULT_MODEL = "claude-opus-4-7"


class ClaudeRequest(BaseModel):
    """Typed request envelope for :meth:`ClaudeProvider.complete`."""

    system: str = Field(description="System prompt.")
    user: str = Field(description="User message.")
    model: str = Field(
        default=_DEFAULT_MODEL,
        description=(
            "Anthropic model id. Defaults to the most-capable current "
            "Claude; callers can pin a smaller / cheaper model "
            "(``claude-haiku-4-5-20251001`` or ``claude-sonnet-4-6``) "
            "per feature."
        ),
    )
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)


class ClaudeResponse(BaseModel):
    """Typed response envelope. Never raises; ``error`` is populated on failure."""

    text: str = Field(default="", description="Assistant reply text.")
    model: str = Field(default="", description="Model id Anthropic served.")
    stop_reason: str = Field(default="", description="Anthropic stop reason.")
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


def is_claude_enabled(api_key: str | None = None) -> bool:
    """``True`` iff an Anthropic API key is available.

    Args:
      api_key: explicit key to check. When ``None``, falls back to the
        ``ANTHROPIC_API_KEY`` env var.
    """
    if api_key:
        return True
    return bool(os.environ.get(_ENV_VAR))


_provider_singleton: ClaudeProvider | None = None
_provider_lock = Lock()


def get_claude_provider(api_key: str | None = None) -> ClaudeProvider:
    """Process-wide singleton :class:`ClaudeProvider`.

    Args:
      api_key: optional key override. When provided, ALWAYS builds a
        new provider — singleton is bypassed so different callers can
        run with different keys (multi-tenant). When ``None``, returns
        the cached singleton (which reads ``ANTHROPIC_API_KEY`` from env
        on first ``complete()``).
    """
    if api_key is not None:
        return ClaudeProvider(api_key=api_key)
    global _provider_singleton
    if _provider_singleton is None:
        with _provider_lock:
            if _provider_singleton is None:
                _provider_singleton = ClaudeProvider()
    return _provider_singleton


def reset_claude_provider() -> None:
    """Test seam: drop the singleton so ``monkeypatch.setenv`` takes effect."""
    global _provider_singleton
    with _provider_lock:
        _provider_singleton = None


class ClaudeProvider:
    """Synchronous one-shot completion against Anthropic's Messages API.

    Construct via :func:`get_claude_provider` (singleton) or directly
    with an explicit ``api_key`` for non-shared use. For tests, pass
    a stub ``client`` to avoid hitting the SDK. :meth:`complete` NEVER
    raises — failures land in :attr:`ClaudeResponse.error`.
    """

    def __init__(
        self,
        *,
        client: Any | None = None,
        api_key: str | None = None,
    ) -> None:
        self._client: Any | None = client
        self._client_init_attempted: bool = client is not None
        self._explicit_api_key: str | None = api_key

    def _ensure_client(self) -> tuple[Any | None, str | None]:
        """Build the SDK client on demand. Returns ``(client, error)``."""
        if self._client is not None:
            return self._client, None

        api_key = self._explicit_api_key or os.environ.get(_ENV_VAR)
        if not api_key:
            return None, f"{_ENV_VAR} is not set and no api_key was passed"

        try:
            # Lazy import so the SDK is not required when this module is
            # imported on a non-Claude deploy.
            from anthropic import Anthropic  # type: ignore[import-not-found]
        except ImportError as exc:
            return None, f"anthropic SDK not installed: {exc}"

        try:
            self._client = Anthropic(api_key=api_key, timeout=_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 — soft-fail per design rule 3
            logger.warning(
                "claude_provider.client_init_failed error=%s",
                str(exc)[:200],
            )
            return None, f"Anthropic client init failed: {str(exc)[:200]}"

        self._client_init_attempted = True
        return self._client, None

    def complete(self, req: ClaudeRequest) -> ClaudeResponse:
        """One-shot synchronous completion. Never raises.

        Retry policy: one extra attempt on 429/5xx with a 1.5s backoff.
        4xx auth errors fail-fast (returning a response with ``error``).
        """
        client, init_err = self._ensure_client()
        if client is None or init_err is not None:
            return ClaudeResponse(
                model=req.model,
                error=init_err or "Anthropic client unavailable",
            )

        kwargs: dict[str, Any] = {
            "model": req.model,
            "system": req.system,
            "messages": [{"role": "user", "content": req.user}],
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
        }

        attempts = 2
        last_err: str | None = None
        for attempt in range(attempts):
            t0 = time.monotonic()
            try:
                response = client.messages.create(**kwargs)
                latency_ms = int((time.monotonic() - t0) * 1000)

                # The SDK returns a list of content blocks; we only ask
                # for text so we concatenate text-typed blocks.
                content_blocks = getattr(response, "content", None) or []
                text_parts: list[str] = []
                for block in content_blocks:
                    block_type = getattr(block, "type", "")
                    if block_type == "text":
                        text_parts.append(getattr(block, "text", "") or "")
                content = "".join(text_parts)

                stop_reason = getattr(response, "stop_reason", "") or ""
                usage = getattr(response, "usage", None)
                in_tok = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
                out_tok = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0

                logger.info(
                    "claude_provider.call model=%s stop=%s in_chars=%d "
                    "out_chars=%d latency_ms=%d in_tok=%d out_tok=%d",
                    req.model, stop_reason,
                    len(req.system) + len(req.user), len(content),
                    latency_ms, in_tok, out_tok,
                )
                return ClaudeResponse(
                    text=content,
                    model=req.model,
                    stop_reason=stop_reason,
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
                    "claude_call_failed model=%s error=%s status=%s "
                    "attempt=%d retryable=%s latency_ms=%d",
                    req.model, str(exc)[:200], status_code,
                    attempt + 1, retryable, latency_ms,
                )
                if not retryable or attempt + 1 >= attempts:
                    return ClaudeResponse(
                        model=req.model, latency_ms=latency_ms,
                        error=last_err,
                    )
                time.sleep(_BACKOFF_S)
                continue

        # Defensive — the loop returns on every path. Belt for mypy.
        return ClaudeResponse(model=req.model, error=last_err or "unknown error")


def _extract_status_code(exc: Exception) -> int | None:
    """Pull an HTTP status code out of an Anthropic SDK exception if present."""
    code = getattr(exc, "status_code", None)
    if code is None:
        # The SDK wraps the underlying httpx response.
        response = getattr(exc, "response", None)
        if response is not None:
            code = getattr(response, "status_code", None)
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
        "APIConnectionError",
        "APITimeoutError",
    }


__all__ = [
    "ClaudeProvider",
    "ClaudeRequest",
    "ClaudeResponse",
    "get_claude_provider",
    "is_claude_enabled",
    "reset_claude_provider",
]
