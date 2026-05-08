from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, Field

from specter.data.articles_existence import ARTICLE_EXISTENCE


class ChatMessage(BaseModel):
    """OpenAI/LiteLLM-style message item.

    Caller provides a conversation history; we extract the final user
    question and optional system context from `role`.
    """

    role: Literal["user", "assistant", "system"]  # only these are meaningful to us
    # P0 #5 — cap at 4K (was 20K). 4K covers any realistic regulatory Q&A
    # while keeping token cost + retrieval-bloat bounded; a 20K prompt-injection
    # would still be quietly accepted at the validation layer pre-fix.
    # Per AskRequest.messages, this cap applies per message — system
    # context + user question + any history each get their own 4K budget.
    content: str = Field(min_length=1, max_length=4_000)


class AskRequest(BaseModel):
    """Specter API request for grounded EU AI Act Q&A."""

    messages: list[ChatMessage] = Field(min_length=1)


class AskResponse(BaseModel):
    """Specter API response (single JSON object).

    Wire shape kept BACKWARDS-COMPATIBLE: ``answer``, ``references``,
    ``reasoning`` were the v1 contract and remain. P0 #3 adds three new
    fields that downstream verifiers can gate on without breaking parsers
    that ignore unknowns:

    - ``confidence`` — 0.0 (no graph data, closed-world refusal) … 0.85
      (rich graph + KB cross-framework signal). Source: ``GraphRAGResponse.confidence``.
    - ``kb_version`` — pinned KB version stamp (``KB_VERSION`` from
      ``app/data/kb.py``). Lets a regulator amendment + cached materialisation
      mismatch be traced.
    - ``retrieval_path`` — one of ``neo4j`` | ``kb_fallback`` | ``deterministic``
      | ``no_match`` so Specter's downstream agent knows whether the answer
      came from the graph, the KB-only fallback, or a closed-world refusal.

    ``reasoning`` is now a structured one-liner instead of the placeholder
    ``"Not scored."`` so legacy parsers display something meaningful.
    """

    answer: str
    references: list[str] = Field(default_factory=list)
    reasoning: str | None = Field(
        default=None,
        description="Human-readable summary of confidence + retrieval path.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "0.0 = closed-world refusal (no matching obligation). "
            "0.85 = rich graph + cross-framework signal."
        ),
    )
    kb_version: str | None = Field(
        default=None,
        description="KB_VERSION pin — see app/data/kb.py.",
    )
    retrieval_path: Literal[
        "neo4j", "kb_fallback", "deterministic", "no_match"
    ] = Field(
        default="kb_fallback",
        description=(
            "Which retrieval layer answered: neo4j (live graph), kb_fallback "
            "(KB derivation when graph cold), deterministic (rule-based "
            "answer when LLM unavailable), no_match (closed-world refusal)."
        ),
    )
    # P1 #9 — surface the underlying graph_stats so a downstream verifier can
    # judge "did retrieval actually find anything?" without re-asking. Source:
    # ``GraphRAGResponse.graph_stats`` (per ``app/engines/graph_rag.py:626``).
    # Defaults are 0 so the closed-world refusal path leaves them at floor.
    nodes_traversed: int = Field(
        default=0,
        ge=0,
        description="Total graph + KB nodes the retrieval layer touched.",
    )
    obligations_found: int = Field(
        default=0,
        ge=0,
        description="Obligations matched by intent + risk + dimension hint.",
    )
    gaps_found: int = Field(
        default=0,
        ge=0,
        description="Compliance gaps discovered during graph reasoning.",
    )


_QUESTION_HASH_SALT = "specter_question_hash_v1"

_ART_RE = re.compile(
    r"^(Art\.|Article)\s*(?P<num>\d+)\s*(?P<tail>.*)$",
    re.IGNORECASE,
)
_ANNEX_RE = re.compile(
    r"^(Annex)\s+(?P<num>[IVXLC]+)\s*(?P<tail>.*)$",
    re.IGNORECASE,
)


def question_hash(question: str) -> str:
    """Hash a Specter question for the evidence-chain forensic field.

    P1 #8 — full sha256 hex (64 chars / 256 bits). The previous 16-hex
    truncation gave 64 bits of collision space — birthday-collision
    territory at scale (~50% probability of one collision after ~4
    billion distinct questions, but adversarial probing concentrates
    far fewer). The full digest costs +48 bytes per evidence row and
    eliminates the concern outright; a forensic search "show me every
    request that asked this exact question" stays one-shot exact-match.

    The salt ``specter_question_hash_v1`` keeps the v1 wire shape — a
    consumer that grepped a 16-char prefix of an old hash still
    matches the same prefix of the new full digest.
    """
    payload = f"{_QUESTION_HASH_SALT}:{question.strip()}".encode()
    return hashlib.sha256(payload).hexdigest()


def _is_known_article_or_annex(raw_ref: str) -> bool:
    """Validate a raw internal ref (e.g. ``Art. 13(1)(a)``) against ARTICLE_EXISTENCE.

    Implements the prefix-fallback semantics from
    ``app/engines/roadmap_refiner/models.py::_is_valid_article_reference`` —
    a citation like ``Art. 13(1)(a)`` is valid when ``Art. 13`` (or ``Art. 13(1)``)
    is in the catalog. Same fallback for ``Annex IV(1)`` against ``Annex IV``.

    Used as a hallucination filter before reshaping a citation for the
    Specter response: if the LLM emits ``Art. 999(z)``, we drop the
    citation rather than format it into a confident-looking ``Article 999.z``.
    """
    raw = (raw_ref or "").strip()
    if not raw:
        return False
    if raw in ARTICLE_EXISTENCE:
        return True
    # Strip nested ``(...)`` suffixes one at a time and re-check. Catches
    # ``Art. 13(1)(a)`` → ``Art. 13(1)`` → ``Art. 13``; ``Annex IV(1)`` → ``Annex IV``.
    candidate = raw
    while "(" in candidate:
        candidate = candidate.rsplit("(", 1)[0].strip()
        if candidate in ARTICLE_EXISTENCE:
            return True
    return False


def reference_from_article_ref(article_ref: str) -> str | None:
    """Convert internal `Art. ...` / `Annex ...` refs into Specter reference strings.

    Examples:
      - "Art. 3(2)" -> "Article 3.2"
      - "Art. 13(1)(a)" -> "Article 13.1.a"
      - "Annex IV(2)" -> "Annex IV.2"

    P0 #2 — validates against ``ARTICLE_EXISTENCE`` BEFORE formatting so
    a hallucinated ``Art. 999(z)`` returns ``None`` instead of being
    confidently reshaped into ``Article 999.z`` and shipped to Specter.
    Drops are silent at this layer (the route caller dedupes + caps refs);
    a future log line could surface the drop count for telemetry.
    """

    raw = (article_ref or "").strip()
    if not raw:
        return None

    # Existence gate first — the regex shapes below would happily turn any
    # well-formed ``Art. <int>(...)`` string into ``Article <int>.<...>``,
    # and the EU AI Act has only 113 articles + 13 Annexes. Reject anything
    # outside the catalog so hallucinations never leave the wire.
    if not _is_known_article_or_annex(raw):
        return None

    annex_m = _ANNEX_RE.match(raw)
    if annex_m:
        annex_roman = annex_m.group("num").upper()
        tail = annex_m.group("tail") or ""
        tokens = re.findall(r"\(([^)]+)\)", tail)
        if not tokens:
            return f"Annex {annex_roman}"
        # Annex sub-points (typically numeric) become "Annex IV.2" form.
        return f"Annex {annex_roman}.{tokens[0].strip()}"

    art_m = _ART_RE.match(raw)
    if not art_m:
        return None

    art_num = art_m.group("num")
    tail = art_m.group("tail") or ""
    tokens = [t.strip() for t in re.findall(r"\(([^)]+)\)", tail) if t.strip()]
    if not tokens:
        return f"Article {int(art_num)}"

    # Specter wants a single dot-separated subpoint chain.
    # - "(2)" -> ".2"
    # - "(1)(a)" -> ".1.a"
    return f"Article {int(art_num)}." + ".".join(tokens)
