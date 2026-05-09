"""Mistral-backed retriever for the Specter Q&A endpoint.

Plugs into :func:`specter.api.qa_route.make_qa_router` as the
``retriever`` argument. When a ``MISTRAL_API_KEY`` is available
(env var or explicit ``api_key=`` parameter), the retriever asks
Mistral La Plateforme to answer the question, grounding the
prompt against the canonical EU AI Act article catalog.

Hallucination posture (preserved from the upstream production
deployment):

* The system prompt enforces "cite ONLY EU AI Act articles you can
  reference verbatim from the provided list" and "if no matching
  obligation is in scope, refuse with `NO_MATCH` so the route's
  closed-world refusal fires."
* Citations the model emits are validated by
  :func:`specter.qa.models.reference_from_article_ref` before
  serialisation; hallucinated articles drop silently.
* When Mistral returns an error, the retriever falls back to a
  minimum-information ``RetrieverResponse`` so the QA route emits
  the deterministic refusal — LLM prose grounded in nothing never
  reaches the wire.

Usage::

    from fastapi import FastAPI
    from specter.api.qa_route import make_qa_router
    from specter.qa.mistral_retriever import make_mistral_retriever

    # Reads MISTRAL_API_KEY from env (default)
    retriever = make_mistral_retriever()

    # Or pass key explicitly
    retriever = make_mistral_retriever(api_key="my-key-...")

    app = FastAPI()
    app.include_router(make_qa_router(retriever=retriever))
    # POST /v1/eu-ai-act/ask is now Mistral-backed.
"""

from __future__ import annotations

import logging

from specter.api.qa_route import RetrieverFn, RetrieverRequest, RetrieverResponse
from specter.llm.mistral_provider import (
    MistralProvider,
    MistralRequest,
    get_mistral_provider,
    is_mistral_enabled,
)
from specter.qa._grounded_prompt import (
    build_system_prompt,
    build_user_prompt,
    empty_refusal_response,
    grounded_response_from_text,
)

logger = logging.getLogger(__name__)


# ─── Retriever factory ────────────────────────────────────────────────────


def make_mistral_retriever(
    *,
    api_key: str | None = None,
    provider: MistralProvider | None = None,
    model: str = "mistral-large-latest",
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> RetrieverFn:
    """Build a :data:`specter.api.qa_route.RetrieverFn` backed by Mistral.

    Args:
      api_key: explicit Mistral API key. When ``None`` (default), reads
        ``MISTRAL_API_KEY`` from the environment. When the host wants
        to ship without env vars (e.g. multi-tenant), pass the key
        explicitly. Library users can wire either:

        ``export MISTRAL_API_KEY=sk-...``  (env-var style — recommended)

        ``make_mistral_retriever(api_key="sk-...")``  (parameter style)

      provider: pre-built :class:`MistralProvider`. Test seam — most
        callers should leave this ``None`` and let the singleton
        manage the SDK client.

      model: Mistral model id. ``mistral-large-latest`` (default) is
        the best regulator-grade output. Pin ``mistral-small-latest``
        for cheaper / faster operation.

      max_tokens / temperature: Mistral generation parameters. Defaults
        match the upstream production deployment.

    Returns:
      A retriever function that the QA route uses verbatim. On
      Mistral failure or no-match, returns the closed-world refusal
      shape so the route emits its deterministic refusal.

    Example::

        from specter.api.qa_route import make_qa_router
        from specter.qa.mistral_retriever import make_mistral_retriever

        retriever = make_mistral_retriever(api_key="sk-...")
        app.include_router(make_qa_router(retriever=retriever))
    """
    # Resolve provider once at factory time — singleton init is cheap
    # and avoids re-reading env on every request.
    if provider is None:
        provider = get_mistral_provider(api_key=api_key)

    system_prompt = build_system_prompt()

    def _retriever(req: RetrieverRequest) -> RetrieverResponse:
        # Defensive: if Mistral isn't configured at request time, fall
        # back to closed-world refusal (the QA route will emit the
        # deterministic no-match string).
        if not is_mistral_enabled(api_key=api_key):
            logger.debug(
                "mistral_retriever.skipped reason=no_key question_chars=%d",
                len(req.question),
            )
            return empty_refusal_response()

        mistral_req = MistralRequest(
            system=system_prompt,
            user=build_user_prompt(req),
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format="json_object",
        )
        mistral_res = provider.complete(mistral_req)

        if mistral_res.error:
            logger.warning(
                "mistral_retriever.error error=%s",
                mistral_res.error[:200] if mistral_res.error else "?",
            )
            return empty_refusal_response()

        return grounded_response_from_text(mistral_res.text)

    return _retriever


__all__ = [
    "make_mistral_retriever",
]
