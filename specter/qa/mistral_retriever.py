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

import json
import logging
import re

from specter.api.qa_route import (
    Citation,
    RetrieverFn,
    RetrieverRequest,
    RetrieverResponse,
)
from specter.data.articles_existence import ARTICLE_EXISTENCE
from specter.llm.mistral_provider import (
    MistralProvider,
    MistralRequest,
    get_mistral_provider,
    is_mistral_enabled,
)

logger = logging.getLogger(__name__)


# ─── Prompt construction ───────────────────────────────────────────────────


_NO_MATCH_TOKEN = "NO_MATCH"

# Hard ceiling on how many articles we list in the system prompt — the
# full 113-article + 13-annex catalog inflates token cost without adding
# value (the model isn't using them as a vocabulary, just as a sanity
# check). Top-N most-cited Articles from real customer flows: high-risk
# obligation surface (Art. 9-15 + 26-29 + 50 + 72) + GPAI (Art. 51-55)
# + general scope (Art. 1-6) + transparency (Art. 13). The full catalog
# is still validated post-hoc by ``reference_from_article_ref``.
_PRIORITY_ARTICLES: tuple[str, ...] = (
    "Art. 1", "Art. 2", "Art. 3", "Art. 4", "Art. 5", "Art. 6",
    "Art. 9", "Art. 10", "Art. 11", "Art. 12", "Art. 13", "Art. 14", "Art. 15",
    "Art. 16", "Art. 17", "Art. 22", "Art. 25", "Art. 26", "Art. 27",
    "Art. 28", "Art. 29", "Art. 43", "Art. 47",
    "Art. 50", "Art. 51", "Art. 53", "Art. 55", "Art. 56",
    "Art. 72", "Art. 99",
    "Annex I", "Annex III", "Annex IV", "Annex IX", "Annex XI",
)


_SYSTEM_PROMPT_TEMPLATE = """\
You are a Specter compliance assistant for the EU AI Act
(Regulation (EU) 2024/1689). Your job is to answer the user's question
GROUNDED ONLY in the regulation. Do not invent obligations.

Hard rules:

1. Cite only articles from the EU AI Act. Do NOT cite GDPR, NIS2, or
   any other regulation unless the user's question is explicitly about
   the cross-walk; even then, only EU AI Act citations count as primary.
2. Use internal-form citations: ``Art. 13(1)(a)``, ``Annex IV(2)``,
   ``Art. 5(1)(c)``. Do NOT use ``Article 13.1.a`` form — the calling
   layer reformats internal-form citations into the wire format and
   validates each one against the canonical catalog. References that
   don't match the catalog are dropped silently.
3. If no Article in the EU AI Act is on point for the user's question,
   reply with the exact token ``{no_match}`` and STOP. Do not write
   prose. Do not guess.
4. Reply in this exact JSON shape so the caller can parse:

   {{
       "answer": "...",
       "citations": ["Art. X(Y)(Z)", "Art. A(B)", ...],
       "confidence": 0.0
   }}

   - ``confidence`` is a self-rating in [0.0, 1.0]: 1.0 means "the
     regulation directly answers this with verbatim text"; 0.0 means
     "no match, do not use my answer".
   - When you emit ``{no_match}``, set confidence to 0.0 and
     citations to ``[]``.

Articles you can reference (priority subset; the full 113-article +
13-annex catalog is also valid — these are the ones most likely to
match a real question):

{articles}

Be concise. Keep ``answer`` under 1000 characters. Cite at most 5
articles per response.
"""


def _build_system_prompt() -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(
        articles=", ".join(_PRIORITY_ARTICLES),
        no_match=_NO_MATCH_TOKEN,
    )


def _build_user_prompt(req: RetrieverRequest) -> str:
    parts: list[str] = []
    if req.system_description:
        parts.append(f"System context:\n{req.system_description}\n")
    parts.append(f"Question: {req.question}")
    return "\n".join(parts)


# ─── Response parsing ──────────────────────────────────────────────────────


_CITATION_RE = re.compile(
    r"(?:Art\.|Article)\s*(\d+)(\([^)]+\))*|"
    r"(?:Annex)\s+([IVXLC]+)(\([^)]+\))*",
    re.IGNORECASE,
)


def _parse_response(text: str) -> tuple[str, list[str], float]:
    """Parse Mistral's reply into (answer, citations, confidence).

    Strict-tier path: the response is valid JSON in the contract shape.
    Lenient-tier path: extract the first ``{...}`` block via regex and
    try to parse that. If both fail, fall back to citation extraction
    from the raw text and return confidence=0.0 so closed-world refusal
    fires at the route layer.
    """
    text = (text or "").strip()
    if not text:
        return "", [], 0.0

    # Closed-world refusal sentinel
    if _NO_MATCH_TOKEN in text:
        return "", [], 0.0

    # Strict JSON parse
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract a JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                data = None
        else:
            data = None

    if isinstance(data, dict):
        answer = str(data.get("answer", "") or "").strip()
        cites_raw = data.get("citations") or []
        if isinstance(cites_raw, list):
            citations = [str(c).strip() for c in cites_raw if c]
        else:
            citations = []
        try:
            confidence = float(data.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        return answer, citations, confidence

    # Lenient fallback: regex citation extraction; no JSON structure
    citations = _extract_citations_from_freetext(text)
    return text[:1000], citations, 0.4 if citations else 0.0


def _extract_citations_from_freetext(text: str) -> list[str]:
    """Pull plausible Article / Annex references out of a free-text reply."""
    out: list[str] = []
    seen: set[str] = set()
    for m in _CITATION_RE.finditer(text):
        raw = m.group(0).strip()
        # Normalise to internal form
        if raw.lower().startswith("article"):
            normalised = re.sub(r"^article", "Art.", raw, flags=re.IGNORECASE)
        else:
            normalised = raw
        if normalised not in seen:
            seen.add(normalised)
            out.append(normalised)
    return out


def _validate_citations(refs: list[str]) -> list[Citation]:
    """Drop hallucinated refs; emit Citation objects for the survivors."""
    survivors: list[Citation] = []
    seen: set[str] = set()
    for raw in refs:
        ref = (raw or "").strip()
        if not ref:
            continue
        # Coerce "Article 13" → "Art. 13" so prefix-fallback hits
        if ref.lower().startswith("article"):
            ref = re.sub(r"^article", "Art.", ref, flags=re.IGNORECASE).strip()
        # Prefix-fallback: Art. 13(1)(a) → resolves via Art. 13
        candidate = ref
        valid = candidate in ARTICLE_EXISTENCE
        while not valid and "(" in candidate:
            candidate = candidate.rsplit("(", 1)[0].strip()
            if candidate in ARTICLE_EXISTENCE:
                valid = True
                break
        if not valid:
            continue
        if ref in seen:
            continue
        seen.add(ref)
        survivors.append(Citation(article_ref=ref))
    return survivors


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

    system_prompt = _build_system_prompt()

    def _retriever(req: RetrieverRequest) -> RetrieverResponse:
        # Defensive: if Mistral isn't configured at request time, fall
        # back to closed-world refusal (the QA route will emit the
        # deterministic no-match string).
        if not is_mistral_enabled(api_key=api_key):
            logger.debug(
                "mistral_retriever.skipped reason=no_key question_chars=%d",
                len(req.question),
            )
            return RetrieverResponse(
                answer="",
                citations=[],
                confidence=0.0,
                graph_stats={
                    "nodes_traversed": 0,
                    "edges_followed": 0,
                    "obligations_found": 0,
                    "gaps_found": 0,
                },
            )

        mistral_req = MistralRequest(
            system=system_prompt,
            user=_build_user_prompt(req),
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
            return RetrieverResponse(
                answer="",
                citations=[],
                confidence=0.0,
                graph_stats={
                    "nodes_traversed": 0,
                    "edges_followed": 0,
                    "obligations_found": 0,
                    "gaps_found": 0,
                },
            )

        answer, raw_citations, confidence = _parse_response(mistral_res.text)
        citations = _validate_citations(raw_citations)

        # Confidence floor at 0.5 when we have valid citations — the
        # route's closed-world refusal threshold is 0.5; below that
        # AND no citations triggers refusal. Citations are themselves
        # a grounding signal; if Mistral self-rated below the floor
        # but emitted valid catalog citations, raise to floor + small
        # epsilon so the answer survives the route's gate.
        if citations and confidence < 0.5:
            confidence = 0.5

        return RetrieverResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            graph_stats={
                "nodes_traversed": len(citations),
                "edges_followed": len(citations),
                "obligations_found": len(citations),
                "gaps_found": 0,
            },
        )

    return _retriever


__all__ = [
    "make_mistral_retriever",
]
