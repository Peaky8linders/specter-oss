"""ComplianceRewardHackDetector — LLM-as-Judge for compliance roadmap proposals.

Implements the six-check reward-hack screen developed for the
Karpathy-style autoresearch loop, decoupled from the host's
roadmap-task registry + KB so it can run in any pipeline.

Six checks, in order:

1. **Plagiarism + origin detection** (SequenceMatcher on prompt vs
   prior-task registry / accepted proposals; ``≥0.80`` reject;
   ``0.50-0.79`` recombination label).
2. **KB reality** (``article_paragraphs`` resolve against the
   regulation catalog; ``dimension_id`` resolves against the host's
   compliance-dimension set).
3. **Coverage plausibility** (per-dimension cap: a single proposal
   can claim at most ``open_questions / total_questions`` worth of
   coverage gain).
4. **Effort sanity** (within ``goal.max_effort_hours_per_task`` and
   above ``0.5h`` floor).
5. **Contract completeness** (≥2 acceptance_criteria, ≥1 output_file,
   ≥1 contract_verification).
6. **Rebutted-excuse match** (token-Jaccard per-sentence; hard matches
   block, soft matches recorded for telemetry).

Per plan-review decision 2B, the detector OWNS the ``origin`` label —
the agent's self-claim is ignored, eliminating the "lying agent
self-labels as agent_novel" attack surface.

Adapted from the upstream Karpathy-style autoresearch loop
(``app/engines/roadmap_refiner/models.py``) for standalone use.

Wiring:

The host supplies these via the ``CompliancePolicy`` callbacks:

* ``article_exists(ref)`` — does this regulation reference resolve?
* ``dimension_exists(dim_id)`` — does this compliance dimension exist?
* ``dimension_open_ratio(dim_id)`` — coverage cap for plausibility check.
* ``registry_prompts()`` — iterable of prior-task prompts (for plagiarism check).
* ``rationalization_entries(article_refs, dim_id)`` — rebutted-excuse table.

Defaults work out of the box for the EU AI Act when the host imports
:mod:`specter.data.articles_existence` + the helpers from this module.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ─── Origin label ──────────────────────────────────────────────────────────


ProposalOrigin = Literal["registry_lift", "recombination", "agent_novel"]


# ─── Loose LLM parse ────────────────────────────────────────────────────────


class RawProposal(BaseModel):
    """Loose shape accepted from the LLM before KB-reality validation.

    The agent is allowed to return extra fields; they are ignored. The
    ``origin`` field, if present, is ALSO ignored — the detector sets
    it deterministically from similarity measurements.
    """

    model_config = ConfigDict(extra="allow")

    task_id: str
    task_title: str = Field(..., description="Short action-phrase")
    description: str
    agent: str = Field(..., description="One of host's agent-role values")
    priority: str = Field(..., description="P0 | P1 | P2")
    effort_hours: float = Field(ge=0)
    dimension_id: str
    prompt: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)
    article_paragraphs: list[str] = Field(default_factory=list)
    contract_verification: list[dict[str, str]] = Field(default_factory=list)
    predicted_coverage_gain: dict[str, float] = Field(default_factory=dict)
    design_rationale: str = ""
    lifecycle_phase: str = "govern"


# ─── Research goal ──────────────────────────────────────────────────────────


class ResearchGoal(BaseModel):
    """What the refinement loop is trying to achieve."""

    target_metric: Literal["coverage_score"] = "coverage_score"
    target_value: float = Field(ge=0.0, le=1.0)
    max_iterations: int = Field(default=30, ge=1)
    early_stop_no_improvement: int = Field(default=5, ge=1)
    improvement_floor: float = Field(default=0.015, ge=0.0, le=1.0)
    kb_dimensions_in_scope: list[str] | None = Field(default=None)
    operator_role: str | None = Field(default=None)
    constraints: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _policy_cap(self) -> Self:
        if self.max_iterations > 100:
            raise ValueError("max_iterations exceeds policy cap of 100")
        return self

    @property
    def max_effort_hours_per_task(self) -> float:
        raw = self.constraints.get("max_effort_hours_per_task", 40)
        return float(raw) if raw else 40.0


# ─── Roadmap proposal (post-promotion form) ────────────────────────────────


class RoadmapProposal(BaseModel):
    """A refiner-proposed remediation task, validated form.

    The OSS package keeps this loose — the host wraps it inside a
    richer task model if needed. Equivalent of the upstream
    ``app.engines.roadmap_refiner.models.RoadmapProposal`` minus the
    ``ClaudeCodeTask`` embedding.
    """

    model_config = ConfigDict(frozen=False)

    proposal_id: str = Field(default_factory=lambda: f"prop-{uuid4().hex[:12]}")
    iteration: int = Field(ge=0)
    parent_proposal_ids: list[str] = Field(default_factory=list)

    # Task data flattened from the raw parse (replaces ClaudeCodeTask embedding).
    task_id: str
    task_title: str
    description: str
    agent: str
    priority: str
    effort_hours: float
    dimension_id: str
    prompt: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)
    article_paragraphs: list[str] = Field(default_factory=list)

    # Metadata
    design_rationale: str = ""
    predicted_coverage_gain: dict[str, float] = Field(default_factory=dict)
    predicted_effort_hours: float = Field(ge=0)
    origin: ProposalOrigin = "agent_novel"  # set by detector


# ─── Rebutted-excuse entry shape ───────────────────────────────────────────


class RationalizationEntry(BaseModel):
    """One row of the rationalization table — an excuse + its rebuttal.

    Match shape compatible with the upstream
    ``app.data.rationalizations`` registry. Hosts that store
    rationalizations in their own format expose them via
    :class:`CompliancePolicy.rationalization_entries`.
    """

    excuse: str
    rebuttal: str = ""
    citation: str = ""
    severity: Literal["hard", "soft"] = "soft"


# ─── Compliance policy (pluggable) ─────────────────────────────────────────


@dataclass
class CompliancePolicy:
    """Pluggable adapter to the host's compliance KB.

    Defaults assume the EU AI Act + dimension-id catalog shipped in
    :mod:`specter.data`. Override any callable to point at a different
    knowledge source (custom regulation, expanded dimension set, etc.).

    All callables are pure — no I/O, deterministic for the same input.
    """

    article_exists: Callable[[str], bool]
    dimension_exists: Callable[[str], bool]
    dimension_open_ratio: Callable[[str], float | None]
    """Returns ``open_questions / total_questions`` for the dimension,
    or None if the dimension has no questions / is unknown."""
    registry_prompts: Callable[[], Iterable[str]] = field(
        default_factory=lambda: (lambda: ())
    )
    """Iterable of prior-task prompts for the plagiarism check.
    Default: empty (every proposal is novel relative to nothing)."""
    rationalization_entries: Callable[
        [list[str], str], list[RationalizationEntry]
    ] = field(default_factory=lambda: (lambda refs, dim_id: []))
    """Returns the rebutted-excuse table for the given article-refs +
    dimension. Default: empty (check 6 is a no-op)."""


# ─── Reward-hack flags ─────────────────────────────────────────────────────


class RewardHackFlags(BaseModel):
    """Result of running all reward-hack checks on a single raw proposal."""

    blocked: bool = False
    reasons: list[str] = Field(default_factory=list)
    origin: ProposalOrigin = "agent_novel"
    max_registry_overlap: float = 0.0
    max_accepted_overlap: float = 0.0
    matched_rationalization_entries: list[str] = Field(default_factory=list)

    def add_block(self, reason: str) -> None:
        self.blocked = True
        self.reasons.append(reason)


# ─── The detector ──────────────────────────────────────────────────────────


class ComplianceRewardHackDetector:
    """LLM-as-Judge for compliance roadmap proposals.

    See module docstring for the full check list. Per plan-review
    decision 2B, this class OWNS the ``origin`` label — the agent's
    self-claim is ignored.
    """

    REGISTRY_OVERLAP_REJECT = 0.80
    RECOMBINATION_MIN = 0.50
    REBUTTED_EXCUSE_JACCARD_THRESHOLD = 0.55

    def __init__(
        self,
        *,
        accepted_proposals: list[RoadmapProposal],
        answers: dict[str, Any],
        goal: ResearchGoal,
        policy: CompliancePolicy,
    ) -> None:
        self._accepted = accepted_proposals
        self._answers = answers
        self._goal = goal
        self._policy = policy

    def check(self, raw: RawProposal) -> RewardHackFlags:
        flags = RewardHackFlags()

        self._check_plagiarism(raw, flags)
        if flags.blocked:
            return flags

        self._check_kb_reality(raw, flags)
        self._check_coverage_plausibility(raw, flags)
        self._check_effort_sanity(raw, flags)
        self._check_contract_completeness(raw, flags)
        self._check_rebutted_excuse(raw, flags)

        return flags

    def _check_plagiarism(self, raw: RawProposal, flags: RewardHackFlags) -> None:
        def _ratio(a: str, b: str) -> float:
            return difflib.SequenceMatcher(None, a, b).ratio()

        max_reg = 0.0
        for prompt in self._policy.registry_prompts():
            r = _ratio(raw.prompt, prompt)
            if r > max_reg:
                max_reg = r

        max_acc = 0.0
        for p in self._accepted:
            r = _ratio(raw.prompt, p.prompt)
            if r > max_acc:
                max_acc = r

        flags.max_registry_overlap = max_reg
        flags.max_accepted_overlap = max_acc

        if max_reg >= self.REGISTRY_OVERLAP_REJECT:
            flags.origin = "registry_lift"
            flags.add_block(
                f"plagiarism: {max_reg:.0%} overlap with prior-task registry entry",
            )
            return

        if max_acc >= self.RECOMBINATION_MIN:
            flags.origin = "recombination"
        else:
            flags.origin = "agent_novel"

    def _check_kb_reality(self, raw: RawProposal, flags: RewardHackFlags) -> None:
        bad_articles = [
            p for p in raw.article_paragraphs
            if not self._policy.article_exists(p)
        ]
        if bad_articles:
            flags.add_block(
                f"kb_reality: article_paragraphs {bad_articles} not found in "
                "the regulation catalog",
            )

        if not self._policy.dimension_exists(raw.dimension_id):
            flags.add_block(
                f"kb_reality: dimension_id '{raw.dimension_id}' is unknown",
            )

        for dim in raw.predicted_coverage_gain:
            if not self._policy.dimension_exists(dim):
                flags.add_block(
                    f"kb_reality: predicted_coverage_gain references unknown dimension '{dim}'",
                )

    def _check_coverage_plausibility(
        self, raw: RawProposal, flags: RewardHackFlags
    ) -> None:
        """Per-dim cap: gain[d] <= open_q_in_d / total_q_in_d."""
        for dim_id, gain in raw.predicted_coverage_gain.items():
            cap = self._policy.dimension_open_ratio(dim_id)
            if cap is None:
                continue
            if gain > cap + 1e-9:
                flags.add_block(
                    f"coverage_plausibility: gain[{dim_id}]={gain:.3f} > "
                    f"open-question ratio {cap:.3f}",
                )

    def _check_effort_sanity(self, raw: RawProposal, flags: RewardHackFlags) -> None:
        if raw.effort_hours < 0.5:
            flags.add_block(f"effort_sanity: effort_hours={raw.effort_hours} < 0.5")
        cap = self._goal.max_effort_hours_per_task
        if raw.effort_hours > cap:
            flags.add_block(
                f"effort_sanity: effort_hours={raw.effort_hours} > cap={cap}",
            )

    def _check_contract_completeness(
        self, raw: RawProposal, flags: RewardHackFlags
    ) -> None:
        if len(raw.acceptance_criteria) < 2:
            flags.add_block(
                f"contract_completeness: acceptance_criteria count "
                f"{len(raw.acceptance_criteria)} < 2",
            )
        if len(raw.output_files) < 1:
            flags.add_block("contract_completeness: output_files empty")
        if len(raw.contract_verification) < 1:
            flags.add_block("contract_completeness: contract_verification empty")

    # ── Check 6: rebutted-excuse match ─────────────────────────────────────

    _SENTENCE_SPLIT_RE = re.compile(r"[.!?]+\s+")
    _TOKENIZE_RE = re.compile(r"[a-z0-9]+")

    @classmethod
    def _tokenize(cls, text: str) -> frozenset[str]:
        tokens = cls._TOKENIZE_RE.findall(text.lower())
        stop = {"the", "a", "an", "and", "or", "but", "of", "to", "in", "on",
                "for", "is", "are", "was", "were", "be", "been", "being",
                "it", "its", "this", "that", "these", "those", "we", "you",
                "our", "your", "by", "with", "as", "at", "from"}
        return frozenset(t for t in tokens if t not in stop)

    @classmethod
    def _jaccard(cls, a: frozenset[str], b: frozenset[str]) -> float:
        if not a or not b:
            return 0.0
        intersection = len(a & b)
        union = len(a | b)
        return intersection / union if union else 0.0

    @classmethod
    def _sentences(cls, text: str) -> list[str]:
        return [s.strip() for s in cls._SENTENCE_SPLIT_RE.split(text) if s.strip()]

    @classmethod
    def _max_sentence_jaccard(cls, excuse: str, target: str) -> float:
        excuse_sentences = cls._sentences(excuse) or [excuse]
        target_sentences = cls._sentences(target) or [target]

        best = 0.0
        for e_sent in excuse_sentences:
            e_tokens = cls._tokenize(e_sent)
            if not e_tokens:
                continue
            for t_sent in target_sentences:
                t_tokens = cls._tokenize(t_sent)
                score = cls._jaccard(e_tokens, t_tokens)
                if score > best:
                    best = score
        return best

    def _check_rebutted_excuse(
        self, raw: RawProposal, flags: RewardHackFlags
    ) -> None:
        """Token Jaccard per-sentence max; threshold 0.55.

        Matchable text is ``task_title`` + ``description`` +
        joined ``acceptance_criteria``. ``design_rationale`` is
        EXCLUDED — that's where the agent explains why it's NOT the
        excuse, so matching against it would inject rebuttal language
        into the match target.

        Severity:
          - ``"hard"`` → block (add to ``flags.reasons``).
          - ``"soft"`` → record in ``matched_rationalization_entries`` only.
        """
        entries = self._policy.rationalization_entries(
            raw.article_paragraphs, raw.dimension_id,
        )
        if not entries:
            return

        matchable_parts = [
            raw.task_title.rstrip("."),
            raw.description.rstrip("."),
            *(ac.rstrip(".") for ac in raw.acceptance_criteria),
        ]
        matchable = ". ".join(p for p in matchable_parts if p)

        for entry in entries:
            score = self._max_sentence_jaccard(entry.excuse, matchable)
            if score >= self.REBUTTED_EXCUSE_JACCARD_THRESHOLD:
                flags.matched_rationalization_entries.append(entry.excuse)
                if entry.severity == "hard":
                    citation = entry.citation or "unknown article"
                    flags.add_block(
                        f"rebutted_excuse: matches '{entry.excuse[:80]}' "
                        f"(jaccard={score:.2f}, cite {citation})",
                    )


# ─── Convenience: EU AI Act default policy ─────────────────────────────────


def make_eu_ai_act_policy(
    *,
    article_existence: frozenset[str],
    valid_dimensions: frozenset[str],
    open_ratio: Callable[[str], float | None] | None = None,
    registry_prompts: Callable[[], Iterable[str]] | None = None,
    rationalization_entries: Callable[[list[str], str], list[RationalizationEntry]] | None = None,
) -> CompliancePolicy:
    """Build a :class:`CompliancePolicy` wired to EU AI Act defaults.

    Args:
        article_existence: frozen set of canonical refs the regulation
          actually contains. See
          :data:`specter.data.articles_existence.ARTICLE_EXISTENCE`.
        valid_dimensions: frozen set of dimension IDs the host KB
          recognises. Hosts using the upstream KB shape pass the dim-id
          set directly.
        open_ratio: optional fn returning ``open / total`` per dim. If
          omitted, coverage-plausibility check returns clean.
        registry_prompts: optional fn returning prior-task prompts for
          plagiarism check. If omitted, all proposals look novel.
        rationalization_entries: optional fn returning the rebutted-excuse
          table. If omitted, check 6 is a no-op.

    Implements the prefix-fallback semantics from the upstream:
    ``Art. 13(1)(a)`` is valid iff ``Art. 13`` (or ``Art. 13(1)``) is
    in the catalog. Same for ``Annex IV(1)`` against ``Annex IV``.
    """

    def _article_exists(ref: str) -> bool:
        raw = (ref or "").strip()
        if not raw:
            return False
        if raw in article_existence:
            return True
        candidate = raw
        while "(" in candidate:
            candidate = candidate.rsplit("(", 1)[0].strip()
            if candidate in article_existence:
                return True
        return False

    def _dimension_exists(dim_id: str) -> bool:
        return dim_id in valid_dimensions

    def _open_ratio(dim_id: str) -> float | None:
        return open_ratio(dim_id) if open_ratio else None

    return CompliancePolicy(
        article_exists=_article_exists,
        dimension_exists=_dimension_exists,
        dimension_open_ratio=_open_ratio,
        registry_prompts=registry_prompts or (lambda: ()),
        rationalization_entries=rationalization_entries
        or (lambda refs, dim_id: []),
    )


__all__ = [
    "CompliancePolicy",
    "ComplianceRewardHackDetector",
    "ProposalOrigin",
    "RationalizationEntry",
    "RawProposal",
    "ResearchGoal",
    "RewardHackFlags",
    "RoadmapProposal",
    "make_eu_ai_act_policy",
]
