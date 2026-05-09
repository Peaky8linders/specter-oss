"""Specter EU AI Act Q&A — grounded partner endpoint (FastAPI route).

Public surface for grounded EU AI Act Q&A. Authentication is OPTIONAL —
the route is reachable without an API key (anonymous tier). Optional
header-based auth unlocks a higher rate-limit tier.

Tier resolution at request time:

* **Privileged tier** — caller sends a valid ``X-Specter-Api-Key`` header
  matching the deploy's configured ``SPECTER_API_KEY``. Rate limit
  60/min keyed on a sha256-truncated hash of the key.
* **Anonymous tier** — no header, or no configured key on this deploy.
  Rate limit 30/min keyed on a 16-hex sha256 hash of the client IP
  (raw IP never persisted — GDPR Art. 4(5) pseudonymisation).

Header present but invalid (typo / stale / wrong tenant) returns 403 —
silent downgrade to anonymous would mask consumer-side bugs.

Backed by a pluggable retriever. Default returns deterministic
closed-world refusal; production deployments inject a real Graph RAG
backend by passing ``retriever=`` to :func:`make_qa_router`.

Hallucination-reduction guards (preserved from upstream):

* **Closed-world refusal** — when retrieval returns no usable context
  (confidence < 0.5 AND no references), emits a deterministic no-match
  response instead of LLM prose grounded in nothing.
* **Reference validation** — every formatted reference is validated
  against the canonical EU AI Act catalog
  (:data:`specter.data.articles_existence.ARTICLE_EXISTENCE`); a
  hallucinated article never reaches the wire.
* **Confidence + KB version + retrieval-path** programmatic fields a
  downstream verifier can gate on.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError
from slowapi import Limiter
from slowapi.util import get_remote_address

from specter.qa.auth import (
    optional_specter_api_key,
    validate_specter_api_key,
)
from specter.qa.models import (
    AskRequest,
    AskResponse,
    question_hash,
    reference_from_article_ref,
)

# Imported lazily inside the request handler to avoid a circular import
# (byok module imports RetrieverFn from this file). The handler resolves
# the per-request retriever from BYOK headers when present and falls
# through to the route's configured default otherwise.
#
# from specter.qa.byok import resolve_request_retriever  # noqa: ERA001

# ─── KB version pin ─────────────────────────────────────────────────────────
# Stamped on every response so a regulator amendment can be traced through
# downstream caches. Keep in lockstep with your KB content version.
KB_VERSION = "2024.1689.v1"


# ─── Pluggable retriever protocol ───────────────────────────────────────────


class RetrieverRequest(BaseModel):
    """Minimal Graph-RAG-style retriever request.

    Hosts wiring a real retriever (Neo4j KG, vector DB, custom rules
    engine, etc.) accept this and return a :class:`RetrieverResponse`.
    """

    question: str = Field(min_length=1, max_length=2_000)
    system_description: str | None = Field(default=None, max_length=1_000)


class Citation(BaseModel):
    article_ref: str = Field(default="")
    snippet: str | None = Field(default=None)


class RetrieverResponse(BaseModel):
    """Minimal Graph-RAG-style retriever response."""

    answer: str = ""
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    graph_stats: dict[str, Any] = Field(default_factory=dict)


RetrieverFn = Callable[[RetrieverRequest], RetrieverResponse]


def _stub_retriever(req: RetrieverRequest) -> RetrieverResponse:
    """Default no-op retriever — always returns closed-world refusal.

    Hosts override this by passing ``retriever=`` to
    :func:`make_qa_router`. The OSS package ships without a graph
    backend so the default is "we have no context" rather than a
    fake answer.
    """
    return RetrieverResponse(
        answer="",
        citations=[],
        confidence=0.0,
        graph_stats={"nodes_traversed": 0, "edges_followed": 0, "obligations_found": 0, "gaps_found": 0},
    )


# ─── Closed-world refusal threshold ─────────────────────────────────────────
# Below this, an answer with empty references gets replaced by a
# structured no-match response. 0.5 is the typical "sparse data" floor;
# below that we have neither graph nor KB context to ground the answer.
_CONFIDENCE_FLOOR_FOR_ANSWER = 0.5

_NO_MATCH_ANSWER = (
    "No matching obligation found in the EU AI Act for this question. "
    "Try rephrasing with a specific article reference (e.g. \"Art. 13\"), "
    "a risk level (e.g. \"high-risk\"), or a compliance dimension "
    "(e.g. \"transparency\")."
)


_RATE_KEY_PREFIX_AUTHED = "specter-key:"
_RATE_KEY_PREFIX_ANON = "specter-anon:"


def _hash16(value: str) -> str:
    """Truncated sha256 hex (16 chars / 64 bits) — pseudonymisation
    helper. Used for partner-key + IP under GDPR Art. 4(5)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _specter_rate_key(request: Request) -> str:
    """Return the rate-limit bucket key for this request.

    Privileged tier: caller sent a valid ``X-Specter-Api-Key`` —
    bucket prefix ``specter-key:`` so 60/min applies.

    Anonymous tier: no header OR no configured key on this deploy —
    bucket prefix ``specter-anon:`` with a 16-hex IP hash so the
    30/min budget is per-source-IP rather than global.

    The two tiers are stored under DIFFERENT keys, so a flood of anon
    traffic cannot exhaust a partner's privileged 60/min budget.
    """
    api_key = request.headers.get("X-Specter-Api-Key", "")
    if api_key and validate_specter_api_key(api_key):
        return f"{_RATE_KEY_PREFIX_AUTHED}{_hash16(api_key)}"
    ip = get_remote_address(request) or "unknown"
    return f"{_RATE_KEY_PREFIX_ANON}{_hash16(ip)}"


def _specter_dynamic_limit(key: str) -> str:
    """Map the rate-limit bucket key to its tier limit string."""
    if key.startswith(_RATE_KEY_PREFIX_AUTHED):
        return "60/minute"
    return "30/minute"


def _reference_rank(formatted: str) -> tuple[int, int, str]:
    """Sort key — Articles before Annexes, more specific paragraph chains first."""
    if formatted.startswith("Article "):
        type_priority = 0
        body = formatted[len("Article ") :]
    elif formatted.startswith("Annex "):
        type_priority = 1
        body = formatted[len("Annex ") :]
    else:
        return (9, 0, formatted)
    specificity = max(0, len(body.split(".")) - 1)
    return (type_priority, -specificity, formatted)


def _resolve_retrieval_path(graph_stats: dict[str, Any]) -> str:
    """Derive the retrieval-path label from the retriever's graph_stats."""
    nodes = int(graph_stats.get("nodes_traversed", 0) or 0)
    edges = int(graph_stats.get("edges_followed", 0) or 0)
    obligations = int(graph_stats.get("obligations_found", 0) or 0)
    gaps = int(graph_stats.get("gaps_found", 0) or 0)

    if edges > 0 or gaps > 0 or obligations > 1:
        return "neo4j"
    if nodes > 0:
        return "kb_fallback"
    return "deterministic"


def _build_reasoning(
    *, confidence: float, kb_version: str, retrieval_path: str, ref_count: int
) -> str:
    return (
        f"Confidence: {confidence:.2f}; KB {kb_version}; "
        f"retrieval: {retrieval_path}; references: {ref_count}"
    )


# ─── Router factory ─────────────────────────────────────────────────────────


def make_qa_router(
    *,
    retriever: RetrieverFn = _stub_retriever,
    limiter: Limiter | None = None,
    kb_version: str = KB_VERSION,
) -> APIRouter:
    """Build the Specter EU AI Act Q&A router.

    Args:
      retriever: pluggable retriever fn — accepts a
        :class:`RetrieverRequest` and returns a :class:`RetrieverResponse`.
        Default returns closed-world refusal so the OSS package ships
        without a graph backend dependency.
      limiter: optional ``slowapi.Limiter``. If omitted, a fresh
        IP-keyed limiter is created — works out of the box but does not
        share state with the host's other rate-limited routes.
      kb_version: the KB content version to stamp on responses. Default
        :data:`KB_VERSION`; override when shipping a custom KB.

    Returns:
      A ``fastapi.APIRouter`` with a single endpoint at
      ``POST /v1/eu-ai-act/ask``.
    """
    if limiter is None:
        limiter = Limiter(key_func=get_remote_address)

    router = APIRouter(tags=["specter-qa"])

    @router.post(
        "/v1/eu-ai-act/ask",
        response_model=AskResponse,
        responses={
            403: {"description": "Invalid API key (header present but did not match)"},
        },
    )
    @limiter.limit(_specter_dynamic_limit, key_func=_specter_rate_key)
    def specter_eu_ai_act_ask(
        request: Request,
        body: Any = Body(...),
        api_key: str | None = Depends(optional_specter_api_key),
    ) -> AskResponse:
        """Specter EU AI Act Q&A endpoint with grounded citations."""

        # Input contract:
        # - primary: request body is `[{role, content}, ...]` (OpenAI/LiteLLM style)
        # - compatibility: `{ "messages": [...] }` or legacy `{ "question": "...", ... }`
        raw_messages: list[dict] | None = None
        if isinstance(body, list):
            raw_messages = body
        elif isinstance(body, dict):
            if "messages" in body:
                raw_messages = body.get("messages")  # type: ignore[assignment]
            elif "question" in body:
                raw_messages = [
                    {"role": "user", "content": body.get("question")},
                ]

        if not raw_messages:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "specter_invalid_input", "message": "Expected messages array."},
            )

        try:
            req = AskRequest.model_validate({"messages": raw_messages})
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "specter_invalid_input",
                    "message": (
                        "Message validation failed. Each message content is "
                        "limited to 4000 characters; role must be one of "
                        "user / assistant / system."
                    ),
                    "errors": exc.errors()[:5],
                },
            ) from exc

        # Extract final user question and optional system context.
        system_parts: list[str] = [m.content for m in req.messages if m.role == "system"]
        system_context = "\n".join(p for p in system_parts if p.strip()) or None

        question = ""
        for m in reversed(req.messages):
            if m.role == "user":
                question = m.content.strip()
                break
        if not question:
            question = req.messages[-1].content.strip()

        # Per-message content cap is 4K (validation). Retriever question prompt
        # is internally truncated to 2 000 characters; system_context to 1 000.
        question = question[:2000]
        if system_context is not None:
            system_context = system_context[:1000]

        rag_req = RetrieverRequest(
            question=question,
            system_description=system_context,
        )

        # BYOK header path: if the caller provided X-Specter-LLM-Provider
        # + X-Specter-LLM-Key, build a one-shot retriever bound to that
        # key for this request only. The key is never persisted; the
        # per-request retriever is garbage-collected at the end of the
        # request. Falls through to the route-level ``retriever`` when
        # no headers are present or the requested provider's SDK is not
        # installed on this deploy.
        from specter.qa.byok import resolve_request_retriever

        active_retriever = resolve_request_retriever(request, default=retriever)
        rag_res = active_retriever(rag_req)

        # Reference validation: bad refs return None and are filtered out.
        # Sort by citation strength (Article > Annex; more specific paragraph
        # chains first), THEN cap at 20 so the strongest citations win even
        # if the retriever emitted weak refs first.
        candidates: list[str] = []
        seen_refs: set[str] = set()
        for c in (rag_res.citations or []):
            ref = getattr(c, "article_ref", "") or ""
            formatted = reference_from_article_ref(ref)
            if not formatted or formatted in seen_refs:
                continue
            seen_refs.add(formatted)
            candidates.append(formatted)
        candidates.sort(key=_reference_rank)
        references: list[str] = candidates[:20]

        confidence = float(getattr(rag_res, "confidence", 0.0) or 0.0)
        retrieval_path = _resolve_retrieval_path(getattr(rag_res, "graph_stats", {}) or {})

        # Closed-world refusal: when we have neither references nor confidence,
        # refuse the answer rather than ship LLM prose grounded in nothing.
        # An answer WITH references at confidence < 0.5 is still returned —
        # the reference list is itself a grounding signal.
        if not references and confidence < _CONFIDENCE_FLOOR_FOR_ANSWER:
            answer_text = _NO_MATCH_ANSWER
            confidence = 0.0
            retrieval_path = "no_match"
        else:
            answer_text = rag_res.answer

        reasoning = _build_reasoning(
            confidence=confidence,
            kb_version=kb_version,
            retrieval_path=retrieval_path,
            ref_count=len(references),
        )

        graph_stats = getattr(rag_res, "graph_stats", {}) or {}
        nodes_traversed = max(0, int(graph_stats.get("nodes_traversed", 0) or 0))
        obligations_found = max(0, int(graph_stats.get("obligations_found", 0) or 0))
        gaps_found = max(0, int(graph_stats.get("gaps_found", 0) or 0))

        return AskResponse(
            answer=answer_text,
            references=references,
            reasoning=reasoning,
            confidence=confidence,
            kb_version=kb_version,
            retrieval_path=retrieval_path,  # type: ignore[arg-type]
            nodes_traversed=nodes_traversed,
            obligations_found=obligations_found,
            gaps_found=gaps_found,
        )

    return router


# Convenience: pre-built router with the stub retriever + default limiter.
qa_router = make_qa_router()


__all__ = [
    "AskRequest",
    "AskResponse",
    "Citation",
    "KB_VERSION",
    "RetrieverFn",
    "RetrieverRequest",
    "RetrieverResponse",
    "make_qa_router",
    "qa_router",
    "question_hash",
]
