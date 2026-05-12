"""Anthropic Claude-backed retriever for the Specter Q&A endpoint.

Plugs into :func:`specter.api.qa_route.make_qa_router` as the
``retriever`` argument. When an ``ANTHROPIC_API_KEY`` is available
(env var or explicit ``api_key=`` parameter), the retriever asks
Claude to answer the question, grounding the prompt against the
canonical EU AI Act article catalog.

Hallucination posture (preserved from the upstream production
deployment): identical to the Claude retriever — system prompt
enforces grounded citations + ``NO_MATCH`` refusal token; emitted
citations validated against ``ARTICLE_EXISTENCE`` before serialisation;
errors fall through to the route's deterministic refusal.

Usage::

    from fastapi import FastAPI
    from specter.api.qa_route import make_qa_router
    from specter.qa.claude_retriever import make_claude_retriever

    # Reads ANTHROPIC_API_KEY from env (default)
    retriever = make_claude_retriever()

    # Or pass key explicitly (BYOK / multi-tenant)
    retriever = make_claude_retriever(api_key="sk-ant-...")

    app = FastAPI()
    app.include_router(make_qa_router(retriever=retriever))
    # POST /v1/eu-ai-act/ask is now Claude-backed.
"""

from __future__ import annotations

import logging

from specter.api.qa_route import RetrieverFn, RetrieverRequest, RetrieverResponse
from specter.llm.claude_provider import (
    ClaudeProvider,
    ClaudeRequest,
    get_claude_provider,
    is_claude_enabled,
)
from specter.qa._grounded_prompt import (
    build_system_prompt,
    build_user_prompt,
    empty_refusal_response,
    grounded_response_from_text,
)

logger = logging.getLogger(__name__)


def make_claude_retriever(
    *,
    api_key: str | None = None,
    provider: ClaudeProvider | None = None,
    model: str = "claude-opus-4-7",
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> RetrieverFn:
    """Build a :data:`specter.api.qa_route.RetrieverFn` backed by Claude.

    Args:
      api_key: explicit Anthropic API key. When ``None`` (default), reads
        ``ANTHROPIC_API_KEY`` from the environment.
      provider: pre-built :class:`ClaudeProvider`. Test seam — most
        callers should leave this ``None`` and let the singleton
        manage the SDK client.
      model: Claude model id. Defaults to the most-capable current
        model; pin a smaller / cheaper model for high-volume traffic.
      max_tokens / temperature: Claude generation parameters.

    Returns:
      A retriever function the QA route uses verbatim. On Claude
      failure or no-match, returns the closed-world refusal shape so
      the route emits its deterministic refusal.
    """
    if provider is None:
        provider = get_claude_provider(api_key=api_key)

    system_prompt = build_system_prompt()

    def _retriever(req: RetrieverRequest) -> RetrieverResponse:
        if not is_claude_enabled(api_key=api_key):
            logger.debug(
                "claude_retriever.skipped reason=no_key question_chars=%d",
                len(req.question),
            )
            return empty_refusal_response()

        claude_req = ClaudeRequest(
            system=system_prompt,
            user=build_user_prompt(req),
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        claude_res = provider.complete(claude_req)

        if claude_res.error:
            logger.warning(
                "claude_retriever.error error=%s",
                claude_res.error[:200] if claude_res.error else "?",
            )
            return empty_refusal_response()

        return grounded_response_from_text(claude_res.text)

    return _retriever


__all__ = ["make_claude_retriever"]
