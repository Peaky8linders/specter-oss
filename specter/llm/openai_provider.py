"""Shared, typed OpenAI ChatGPT provider for Specter.

Used by:

* :mod:`specter.qa.openai_retriever` — OpenAI-backed retriever for the
  public Q&A endpoint at :func:`specter.api.qa_route.make_qa_router`.

Design rules (kept in lockstep with claude_provider):

1. Lazy-init the SDK on first ``complete()``. Importing this module
   never raises if neither ``OPENAI_API_KEY`` nor ``api_key=...`` is
   set; hosts on a non-OpenAI deploy can still ``import specter.llm``.
2. Read the key from ``os.environ`` directly — explicit ``api_key=``
   wins over the env var. Re-reading per-call matches the operator-
   friendly pattern: an env-var rebind on the deploy target takes
   effect on the next request, not the next deploy.
3. NEVER raise from ``complete()`` — return a :class:`OpenAIResponse`
   with ``error`` populated. Callers always have a fallback (closed-
   world refusal in the QA retriever).
4. Retry once on transient (HTTP 429 / 5xx / network blip) with a 1.5s
   backoff. Do NOT retry on 4xx auth — that is a config error.
5. Every call emits a structured log line (``openai_provider.call``).

Out of scope:

* Streaming, tool calling, async — same boundaries as the other two
  providers.
"""

from __future__ import annotations

import logging
import os
import time
from threading import Lock
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_BACKOFF_S = 1.5
_TIMEOUT_S = 30.0

_ENV_VAR = "OPENAI_API_KEY"

# Default model: keep this on the latest stable family. Callers pin a
# cheaper model per-feature when latency dominates over capability.
_DEFAULT_MODEL = "gpt-4o"


class OpenAIRequest(BaseModel):
    """Typed request envelope for :meth:`OpenAIProvider.complete`."""

    system: str = Field(description="System prompt.")
    user: str = Field(description="User message.")
    model: str = Field(
        default=_DEFAULT_MODEL,
        description=(
            "OpenAI model id. Defaults to ``gpt-4o``; callers can pin "
            "``gpt-4o-mini`` for cheaper / faster operation."
        ),
    )
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    response_format: Literal["text", "json_object"] = Field(default="text")


class OpenAIResponse(BaseModel):
    """Typed response envelope. Never raises; ``error`` is populated on failure."""

    text: str = Field(default="", description="Assistant reply text.")
    model: str = Field(default="", description="Model id OpenAI served.")
    finish_reason: str = Field(default="", description="OpenAI stop reason.")
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


def is_openai_enabled(api_key: str | None = None) -> bool:
    """``True`` iff an OpenAI API key is available.

    Args:
      api_key: explicit key to check. When ``None``, falls back to the
        ``OPENAI_API_KEY`` env var.
    """
    if api_key:
        return True
    return bool(os.environ.get(_ENV_VAR))


_provider_singleton: OpenAIProvider | None = None
_provider_lock = Lock()


def get_openai_provider(api_key: str | None = None) -> OpenAIProvider:
    """Process-wide singleton :class:`OpenAIProvider`.

    Args:
      api_key: optional key override. When provided, ALWAYS builds a
        new provider — singleton is bypassed so different callers can
        run with different keys (multi-tenant). When ``None``, returns
        the cached singleton (which reads ``OPENAI_API_KEY`` from env
        on first ``complete()``).
    """
    if api_key is not None:
        return OpenAIProvider(api_key=api_key)
    global _provider_singleton
    if _provider_singleton is None:
        with _provider_lock:
            if _provider_singleton is None:
                _provider_singleton = OpenAIProvider()
    return _provider_singleton


def reset_openai_provider() -> None:
    """Test seam: drop the singleton so ``monkeypatch.setenv`` takes effect."""
    global _provider_singleton
    with _provider_lock:
        _provider_singleton = None


class OpenAIProvider:
    """Synchronous one-shot completion against OpenAI's Chat Completions API.

    Construct via :func:`get_openai_provider` (singleton) or directly
    with an explicit ``api_key`` for non-shared use. For tests, pass
    a stub ``client`` to avoid hitting the SDK. :meth:`complete` NEVER
    raises — failures land in :attr:`OpenAIResponse.error`.
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
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            return None, f"openai SDK not installed: {exc}"

        try:
            self._client = OpenAI(api_key=api_key, timeout=_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 — soft-fail per design rule 3
            logger.warning(
                "openai_provider.client_init_failed error=%s",
                str(exc)[:200],
            )
            return None, f"OpenAI client init failed: {str(exc)[:200]}"

        self._client_init_attempted = True
        return self._client, None

    def complete(self, req: OpenAIRequest) -> OpenAIResponse:
        """One-shot synchronous completion. Never raises.

        Retry policy: one extra attempt on 429/5xx with a 1.5s backoff.
        4xx auth errors fail-fast (returning a response with ``error``).
        """
        client, init_err = self._ensure_client()
        if client is None or init_err is not None:
            return OpenAIResponse(
                model=req.model,
                error=init_err or "OpenAI client unavailable",
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

        attempts = 2
        last_err: str | None = None
        for attempt in range(attempts):
            t0 = time.monotonic()
            try:
                response = client.chat.completions.create(**kwargs)
                latency_ms = int((time.monotonic() - t0) * 1000)
                if not getattr(response, "choices", None):
                    last_err = "OpenAI returned no choices"
                    logger.warning(
                        "openai_provider.empty_response model=%s latency_ms=%d",
                        req.model, latency_ms,
                    )
                    if attempt + 1 < attempts:
                        time.sleep(_BACKOFF_S)
                        continue
                    return OpenAIResponse(
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
                    "openai_provider.call model=%s finish=%s in_chars=%d "
                    "out_chars=%d latency_ms=%d in_tok=%d out_tok=%d",
                    req.model, finish_reason,
                    len(req.system) + len(req.user), len(content),
                    latency_ms, in_tok, out_tok,
                )
                return OpenAIResponse(
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
                    "openai_call_failed model=%s error=%s status=%s "
                    "attempt=%d retryable=%s latency_ms=%d",
                    req.model, str(exc)[:200], status_code,
                    attempt + 1, retryable, latency_ms,
                )
                if not retryable or attempt + 1 >= attempts:
                    return OpenAIResponse(
                        model=req.model, latency_ms=latency_ms,
                        error=last_err,
                    )
                time.sleep(_BACKOFF_S)
                continue

        return OpenAIResponse(model=req.model, error=last_err or "unknown error")


def _extract_status_code(exc: Exception) -> int | None:
    """Pull an HTTP status code out of an OpenAI SDK exception if present."""
    code = getattr(exc, "status_code", None)
    if code is None:
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
    "OpenAIProvider",
    "OpenAIRequest",
    "OpenAIResponse",
    "get_openai_provider",
    "is_openai_enabled",
    "reset_openai_provider",
]
