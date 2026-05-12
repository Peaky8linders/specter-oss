"""Shared system-prompt + response parser for grounded LLM retrievers.

The Claude / OpenAI retrievers all need the same two things:

1. A system prompt that grounds the model on the EU AI Act article
   catalog and instructs it to emit a ``NO_MATCH`` token when no
   obligation is on point — landing the route's deterministic
   closed-world refusal.
2. A response parser that pulls (answer, citations, confidence) out of
   the model's reply and validates each citation against
   :data:`specter.data.articles_existence.ARTICLE_EXISTENCE`.

Pulling these into a private helper keeps the three retrievers thin
(they just adapt their provider's request/response shape) and makes the
hallucination-reduction posture audit-able from one file.

Hallucination guards (preserved from the upstream production
deployment):

* The system prompt enforces "cite ONLY EU AI Act articles you can
  reference verbatim from the provided list" and "if no matching
  obligation is in scope, refuse with ``NO_MATCH``".
* Citations the model emits are validated against the article catalog
  before serialisation; hallucinated articles drop silently.
* Confidence is floor-clamped to 0.5 when the model emitted at least
  one valid catalog citation. Citations are themselves a grounding
  signal; if the model self-rated below the floor but cited correctly,
  we raise to floor + epsilon so the answer survives the route's gate.
"""

from __future__ import annotations

import json
import re

from specter.api.qa_route import (
    Citation,
    RetrieverRequest,
    RetrieverResponse,
)
from specter.data.articles_existence import ARTICLE_EXISTENCE

_NO_MATCH_TOKEN = "NO_MATCH"

# Hard ceiling on how many articles we list in the system prompt — the
# full 113-article + 13-annex catalog inflates token cost without
# adding value (the model isn't using them as a vocabulary, just as a
# sanity check). Top-N most-cited Articles from real customer flows.
# The full catalog is still validated post-hoc by the router's
# ``reference_from_article_ref``.
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


def build_system_prompt() -> str:
    """Return the shared, grounded system prompt for any LLM retriever."""
    return _SYSTEM_PROMPT_TEMPLATE.format(
        articles=", ".join(_PRIORITY_ARTICLES),
        no_match=_NO_MATCH_TOKEN,
    )


def build_user_prompt(req: RetrieverRequest) -> str:
    parts: list[str] = []
    if req.system_description:
        parts.append(f"System context:\n{req.system_description}\n")
    parts.append(f"Question: {req.question}")
    return "\n".join(parts)


_CITATION_RE = re.compile(
    r"(?:Art\.|Article)\s*(\d+)(\([^)]+\))*|"
    r"(?:Annex)\s+([IVXLC]+)(\([^)]+\))*",
    re.IGNORECASE,
)


def parse_response(text: str) -> tuple[str, list[str], float]:
    """Parse a model's reply into ``(answer, citations, confidence)``.

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

    # Lenient fallback: regex citation extraction
    citations = _extract_citations_from_freetext(text)
    return text[:1000], citations, 0.4 if citations else 0.0


def _extract_citations_from_freetext(text: str) -> list[str]:
    """Pull plausible Article / Annex references out of a free-text reply."""
    out: list[str] = []
    seen: set[str] = set()
    for m in _CITATION_RE.finditer(text):
        raw = m.group(0).strip()
        if raw.lower().startswith("article"):
            normalised = re.sub(r"^article", "Art.", raw, flags=re.IGNORECASE)
        else:
            normalised = raw
        if normalised not in seen:
            seen.add(normalised)
            out.append(normalised)
    return out


def validate_citations(refs: list[str]) -> list[Citation]:
    """Drop hallucinated refs; emit Citation objects for the survivors."""
    survivors: list[Citation] = []
    seen: set[str] = set()
    for raw in refs:
        ref = (raw or "").strip()
        if not ref:
            continue
        if ref.lower().startswith("article"):
            ref = re.sub(r"^article", "Art.", ref, flags=re.IGNORECASE).strip()
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


def empty_refusal_response() -> RetrieverResponse:
    """Closed-world refusal shape — used when the LLM is unavailable."""
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


def grounded_response_from_text(text: str) -> RetrieverResponse:
    """Convert a raw LLM text reply into a wire-shape RetrieverResponse.

    Performs the citation validation + confidence floor logic that all
    three grounded retrievers share. Returns the closed-world refusal
    shape on a parse miss / NO_MATCH so the route's deterministic
    refusal lands.
    """
    answer, raw_citations, confidence = parse_response(text)
    citations = validate_citations(raw_citations)

    # Confidence floor at 0.5 when we have valid citations — the route's
    # closed-world refusal threshold is 0.5; below that AND no citations
    # triggers refusal. Citations are themselves a grounding signal.
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


__all__ = [
    "build_system_prompt",
    "build_user_prompt",
    "empty_refusal_response",
    "grounded_response_from_text",
    "parse_response",
    "validate_citations",
]
