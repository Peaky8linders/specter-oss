"""APTS conformance scoring engine.

Reads the vendored 173-requirement catalog and the curated evidence map,
then emits a structured ``ConformanceReport`` that:

* Aggregates per-requirement results into a per-domain summary (8 domains).
* Computes per-tier readiness — a tier is "achieved" only when every MUST
  requirement at or below that tier is ``satisfied``. SHOULDs are advisory;
  they're surfaced in the report but don't gate tier achievement.
* Produces a stable headline percentage per tier (satisfied + 0.5 × partial,
  weighted MUST=1 / SHOULD=0.5 to mirror the upstream weighting prose).
* Links every result back to the evidence module path + test anchor so an
  auditor can verify each claim independently.

The engine is pure-functional + deterministic: same inputs → same report.
The ``assess_self`` entry-point uses the curated map as the input set; the
``assess_target`` entry-point lets callers override claims for a specific
target system (e.g. an external pentesting platform claiming APTS conformance).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from specter.apts.evidence_map import EvidenceClaim, get_evidence_map
from specter.apts.models import APTSDomain, APTSRequirement, APTSTier
from specter.apts.requirements import (
    APTS_VERSION,
    list_domains,
    load_requirements,
)

ConformanceLevel = Literal["satisfied", "partial", "gap", "unmapped"]

# Per-classification weight in the headline percentage. MUSTs count fully;
# SHOULDs are advisory + half-weighted so a platform that satisfies every
# MUST but no SHOULD still scores well, and a platform that only satisfies
# SHOULDs scores poorly. Matches the upstream wording that SHOULDs are
# "additional advisory practices".
_WEIGHT: dict[str, float] = {"MUST": 1.0, "SHOULD": 0.5}

# Per-level credit. Satisfied gets full credit, partial gets half, gap zero.
_CREDIT: dict[ConformanceLevel, float] = {
    "satisfied": 1.0,
    "partial": 0.5,
    "gap": 0.0,
    "unmapped": 0.0,
}


@dataclass(frozen=True)
class RequirementResult:
    """One row in a ``ConformanceReport``."""

    requirement_id: str
    domain: APTSDomain
    tier: APTSTier
    classification: str  # "MUST" | "SHOULD"
    title: str
    level: ConformanceLevel
    rationale: str
    modules: tuple[str, ...]
    test_anchors: tuple[str, ...]
    article_anchors: tuple[str, ...]


@dataclass(frozen=True)
class DomainSummary:
    """Per-domain rollup for the dashboard heatmap."""

    domain: APTSDomain
    total: int
    satisfied: int
    partial: int
    gap: int
    unmapped: int
    must_satisfied: int
    must_total: int
    coverage_score: float  # 0.0-1.0


@dataclass(frozen=True)
class TierStatus:
    """Per-tier readiness — Tier achieved iff every MUST is ``satisfied``.

    ``coverage_score`` includes partials at half-weight so a platform that
    is *almost* at a tier still has a meaningful number to ladder against.
    """

    tier: APTSTier
    label: str
    must_total: int
    must_satisfied: int
    must_partial: int
    must_gap: int
    should_total: int
    should_satisfied: int
    should_partial: int
    should_gap: int
    achieved: bool  # True iff every MUST at this tier (and below) is satisfied
    coverage_score: float  # 0.0-1.0


@dataclass(frozen=True)
class ConformanceReport:
    """Top-level conformance assessment for one target."""

    target_id: str
    """Stable identifier for the assessed system (e.g. tenant/system audit_result_id)."""

    target_label: str
    """Human-readable label shown in the UI (e.g. system_name)."""

    apts_version: str
    generated_at: datetime
    requirement_results: tuple[RequirementResult, ...]
    domain_summaries: tuple[DomainSummary, ...]
    tier_status: tuple[TierStatus, ...]

    headline_score: float
    """Overall headline 0.0-1.0 score across all 173 requirements (weighted)."""

    headline_tier: APTSTier | None
    """Highest tier achieved; ``None`` if not even Tier 1 is achieved."""

    counts: dict[str, int]
    """Aggregate counters: total / satisfied / partial / gap / unmapped."""


# ─── Public entrypoints ─────────────────────────────────────────────────────


def assess_self(
    *,
    target_id: str = "reference-platform",
    target_label: str = "Reference platform",
) -> ConformanceReport:
    """Assess the platform itself against APTS using the curated evidence map.

    Stable + deterministic: every call produces the same report shape (modulo
    ``generated_at``). Used by ``GET /api/v1/apts/conformance/self`` and the
    Cybersec Agents Hub default-scanner card.
    """
    return _build_report(
        target_id=target_id,
        target_label=target_label,
        claims=get_evidence_map().values(),
    )


def assess_target(
    *,
    target_id: str,
    target_label: str,
    overrides: Iterable[EvidenceClaim] = (),
) -> ConformanceReport:
    """Assess a target system, starting from the platform's curated map.

    ``overrides`` lets a caller restate specific requirement IDs (e.g. flip
    ``APTS-AL-027`` from ``gap`` to ``satisfied`` for a target that genuinely
    needs stealth-mode operation). Any requirement not overridden inherits
    the platform's curated claim; any not in the curated map at all is
    surfaced as ``unmapped`` so the report never silently treats a missing
    claim as a satisfied one.
    """
    by_id = dict(get_evidence_map())
    for override in overrides:
        by_id[override.requirement_id] = override
    return _build_report(
        target_id=target_id,
        target_label=target_label,
        claims=by_id.values(),
    )


# ─── Internals ──────────────────────────────────────────────────────────────


def _build_report(
    *,
    target_id: str,
    target_label: str,
    claims: Iterable[EvidenceClaim],
) -> ConformanceReport:
    by_id = {c.requirement_id: c for c in claims}
    requirements = load_requirements()

    results = tuple(_to_result(req, by_id.get(req.id)) for req in requirements)
    domain_summaries = tuple(_summarise_domain(d, results) for d in list_domains())
    tier_status = tuple(_summarise_tier(t, results) for t in APTSTier)

    headline_score = _headline_score(results)
    headline_tier = _highest_achieved_tier(tier_status)
    counts = _counts(results)

    return ConformanceReport(
        target_id=target_id,
        target_label=target_label,
        apts_version=APTS_VERSION,
        generated_at=datetime.now(UTC),
        requirement_results=results,
        domain_summaries=domain_summaries,
        tier_status=tier_status,
        headline_score=headline_score,
        headline_tier=headline_tier,
        counts=counts,
    )


def _to_result(
    req: APTSRequirement, claim: EvidenceClaim | None
) -> RequirementResult:
    if claim is None:
        return RequirementResult(
            requirement_id=req.id,
            domain=req.domain,
            tier=req.tier,
            classification=req.classification,
            title=req.title,
            level="unmapped",
            rationale="No evidence claim recorded for this requirement.",
            modules=(),
            test_anchors=(),
            article_anchors=(),
        )
    return RequirementResult(
        requirement_id=req.id,
        domain=req.domain,
        tier=req.tier,
        classification=req.classification,
        title=req.title,
        level=claim.level,
        rationale=claim.rationale,
        modules=claim.modules,
        test_anchors=claim.test_anchors,
        article_anchors=claim.article_anchors,
    )


def _summarise_domain(
    domain: APTSDomain, results: tuple[RequirementResult, ...]
) -> DomainSummary:
    rows = [r for r in results if r.domain == domain]
    levels = Counter(r.level for r in rows)
    must_rows = [r for r in rows if r.classification == "MUST"]
    must_satisfied = sum(1 for r in must_rows if r.level == "satisfied")
    coverage = (
        sum(_WEIGHT[r.classification] * _CREDIT[r.level] for r in rows)
        / sum(_WEIGHT[r.classification] for r in rows)
        if rows
        else 0.0
    )
    return DomainSummary(
        domain=domain,
        total=len(rows),
        satisfied=levels.get("satisfied", 0),
        partial=levels.get("partial", 0),
        gap=levels.get("gap", 0),
        unmapped=levels.get("unmapped", 0),
        must_satisfied=must_satisfied,
        must_total=len(must_rows),
        coverage_score=round(coverage, 4),
    )


def _summarise_tier(
    tier: APTSTier, results: tuple[RequirementResult, ...]
) -> TierStatus:
    # Tier achievement is cumulative: Tier-2 requires every Tier-1 + Tier-2
    # MUST. Tier-3 requires every Tier-1 + Tier-2 + Tier-3 MUST.
    in_scope = [r for r in results if r.tier.value <= tier.value]
    must_rows = [r for r in in_scope if r.classification == "MUST"]
    should_rows = [r for r in in_scope if r.classification == "SHOULD"]

    must_levels = Counter(r.level for r in must_rows)
    should_levels = Counter(r.level for r in should_rows)

    must_satisfied = must_levels.get("satisfied", 0)
    must_partial = must_levels.get("partial", 0)
    must_gap = must_levels.get("gap", 0) + must_levels.get("unmapped", 0)

    should_satisfied = should_levels.get("satisfied", 0)
    should_partial = should_levels.get("partial", 0)
    should_gap = should_levels.get("gap", 0) + should_levels.get("unmapped", 0)

    achieved = must_satisfied == len(must_rows)

    coverage = (
        sum(_WEIGHT[r.classification] * _CREDIT[r.level] for r in in_scope)
        / sum(_WEIGHT[r.classification] for r in in_scope)
        if in_scope
        else 0.0
    )

    return TierStatus(
        tier=tier,
        label={
            APTSTier.foundation: "Tier 1 — Foundation",
            APTSTier.verified: "Tier 2 — Verified",
            APTSTier.comprehensive: "Tier 3 — Comprehensive",
        }[tier],
        must_total=len(must_rows),
        must_satisfied=must_satisfied,
        must_partial=must_partial,
        must_gap=must_gap,
        should_total=len(should_rows),
        should_satisfied=should_satisfied,
        should_partial=should_partial,
        should_gap=should_gap,
        achieved=achieved,
        coverage_score=round(coverage, 4),
    )


def _highest_achieved_tier(tier_status: tuple[TierStatus, ...]) -> APTSTier | None:
    achieved: list[APTSTier] = [t.tier for t in tier_status if t.achieved]
    return max(achieved, key=lambda t: t.value) if achieved else None


def _headline_score(results: tuple[RequirementResult, ...]) -> float:
    if not results:
        return 0.0
    numerator = sum(_WEIGHT[r.classification] * _CREDIT[r.level] for r in results)
    denominator = sum(_WEIGHT[r.classification] for r in results)
    return round(numerator / denominator, 4) if denominator else 0.0


def _counts(results: tuple[RequirementResult, ...]) -> dict[str, int]:
    levels = Counter(r.level for r in results)
    must_rows = [r for r in results if r.classification == "MUST"]
    must_satisfied = sum(1 for r in must_rows if r.level == "satisfied")
    return {
        "total": len(results),
        "satisfied": levels.get("satisfied", 0),
        "partial": levels.get("partial", 0),
        "gap": levels.get("gap", 0),
        "unmapped": levels.get("unmapped", 0),
        "must_total": len(must_rows),
        "must_satisfied": must_satisfied,
    }
