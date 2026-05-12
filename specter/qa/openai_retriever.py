"""OpenAI ChatGPT-backed retriever for the Specter Q&A endpoint.

Plugs into :func:`specter.api.qa_route.make_qa_router` as the
``retriever`` argument. When an ``OPENAI_API_KEY`` is available
(env var or explicit ``api_key=`` parameter), the retriever asks
ChatGPT to answer the question, grounding the prompt against the
canonical EU AI Act article catalog.

Hallucination posture identical to the Claude retriever —
system prompt enforces grounded citations + ``NO_MATCH`` refusal token;
emitted citations validated against ``ARTICLE_EXISTENCE`` before
serialisation; errors fall through to the route's deterministic
refusal.

Usage::

    from fastapi import FastAPI
    from specter.api.qa_route import make_qa_router
    from specter.qa.openai_retriever import make_openai_retriever

    # Reads OPENAI_API_KEY from env (default)
    retriever = make_openai_retriever()

    # Or pass key explicitly (BYOK / multi-tenant)
    retriever = make_openai_retriever(api_key="sk-...")

    app = FastAPI()
    app.include_router(make_qa_router(retriever=retriever))
    # POST /v1/eu-ai-act/ask is now ChatGPT-backed.
"""

from __future__ import annotations

import logging

from specter.api.qa_route import RetrieverFn, RetrieverRequest, RetrieverResponse
from specter.llm.openai_provider import (
    OpenAIProvider,
    OpenAIRequest,
    get_openai_provider,
    is_openai_enabled,
)
from specter.qa._grounded_prompt import (
    build_system_prompt,
    build_user_prompt,
    empty_refusal_response,
    grounded_response_from_text,
)

logger = logging.getLogger(__name__)


def make_openai_retriever(
    *,
    api_key: str | None = None,
    provider: OpenAIProvider | None = None,
    model: str = "gpt-4o",
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> RetrieverFn:
    """Build a :data:`specter.api.qa_route.RetrieverFn` backed by OpenAI.

    Args:
      api_key: explicit OpenAI API key. When ``None`` (default), reads
        ``OPENAI_API_KEY`` from the environment.
      provider: pre-built :class:`OpenAIProvider`. Test seam — most
        callers should leave this ``None`` and let the singleton
        manage the SDK client.
      model: OpenAI model id. ``gpt-4o`` (default) for best output;
        pin ``gpt-4o-mini`` for cheaper / faster operation.
      max_tokens / temperature: OpenAI generation parameters.

    Returns:
      A retriever function the QA route uses verbatim. On OpenAI
      failure or no-match, returns the closed-world refusal shape so
      the route emits its deterministic refusal.
    """
    if provider is None:
        provider = get_openai_provider(api_key=api_key)

    system_prompt = build_system_prompt()

    def _retriever(req: RetrieverRequest) -> RetrieverResponse:
        if not is_openai_enabled(api_key=api_key):
            logger.debug(
                "openai_retriever.skipped reason=no_key question_chars=%d",
                len(req.question),
            )
            return empty_refusal_response()

        oai_req = OpenAIRequest(
            system=system_prompt,
            user=build_user_prompt(req),
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format="json_object",
        )
        oai_res = provider.complete(oai_req)

        if oai_res.error:
            logger.warning(
                "openai_retriever.error error=%s",
                oai_res.error[:200] if oai_res.error else "?",
            )
            return empty_refusal_response()

        return grounded_response_from_text(oai_res.text)

    return _retriever


__all__ = ["make_openai_retriever"]
