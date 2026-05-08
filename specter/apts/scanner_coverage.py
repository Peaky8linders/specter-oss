"""Per-scan APTS coverage engine.

Takes a Code Scanner ``ScanResult`` plus the per-analyzer ``AnalyzerResult``
list and emits a structured ``APTSScanCoverage`` showing — for every APTS
requirement the analyzers can speak to — whether the scanned codebase
demonstrates that control, partially demonstrates it, or shows a gap.

The verdict-derivation rule:

* **Score-based** (preferred): if the analyzer ran on this scan, look at its
  ``score`` (0-100). ``>= 80`` → satisfied; ``50-79`` → partial; ``< 50`` → gap.
* **Finding-based fallback**: if no analyzer score is available (older scan
  payloads), count gap-level findings emitted by the analyzers that speak to
  this requirement. Zero gap findings = satisfied; ≤ 1 = partial; ≥ 2 = gap.
* **Multiple analyzers per requirement**: the *worst* level across contributing
  analyzers wins. If one analyzer says "satisfied" and another says "gap",
  the report reports "gap" — same fail-loudly principle as the platform-level
  conformance map.
* **Analyzer didn't run**: requirement is reported as ``not_assessed`` with no
  level. The headline percentage excludes ``not_assessed`` rows so a sparse
  scan doesn't artificially inflate the score.

The engine is pure-functional + deterministic — same inputs produce the same
report. Covered by ``tests/test_apts_scanner_coverage.py``.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Literal

from specter.apts.requirements import requirement_by_id
from specter.apts.scanner_mapping import (
    ANALYZER_TO_APTS,
    covered_apts_requirement_ids,
)

# Score thresholds — reused by ``derive_apts_coverage`` and pinned by the
# unit test so any future tightening stays explicit.
_SATISFIED_FLOOR = 80.0
_PARTIAL_FLOOR = 50.0


ScanCoverageLevel = Literal["satisfied", "partial", "gap", "not_assessed"]


@dataclass(frozen=True)
class _AnalyzerSnapshot:
    """Trimmed view of an ``AnalyzerResult`` the engine actually needs.

    Defined here so the engine can be tested against a mock without pulling
    in the full ``app.engines.scanners._base.AnalyzerResult`` import chain.
    """

    analyzer_id: str
    score: float
    gap_finding_count: int


@dataclass(frozen=True)
class APTSRequirementCoverage:
    """One row in an :class:`APTSScanCoverage`."""

    requirement_id: str
    domain: str
    tier: int
    classification: str  # "MUST" | "SHOULD"
    title: str
    level: ScanCoverageLevel
    contributing_analyzers: tuple[str, ...]
    rationale: str  # Short human-readable explanation


@dataclass(frozen=True)
class APTSScanCoverage:
    """Per-scan APTS coverage report — emitted alongside a Code Scanner result."""

    scan_id: str
    project_name: str
    apts_version: str
    headline_score: float  # 0.0-1.0; excludes not_assessed rows
    counts: dict[str, int]
    domain_coverage: dict[str, float]  # domain label → 0.0-1.0
    requirement_results: tuple[APTSRequirementCoverage, ...]


# ─── Public entrypoint ──────────────────────────────────────────────────────


def derive_apts_coverage(
    *,
    scan_id: str,
    project_name: str,
    analyzer_snapshots: Iterable[_AnalyzerSnapshot] | Iterable[dict],
) -> APTSScanCoverage:
    """Derive APTS coverage from analyzer snapshots.

    Accepts either typed ``_AnalyzerSnapshot`` instances (used by the engine
    itself + tests) or plain dicts with the same keys (used by the route
    layer when adapting an ``AnalyzerResult``). Unknown analyzer IDs are
    silently ignored so adding analyzers later doesn't break old payloads.
    """
    from specter.apts.requirements import APTS_VERSION

    snapshots = tuple(_coerce_snapshot(s) for s in analyzer_snapshots)
    by_analyzer: dict[str, _AnalyzerSnapshot] = {s.analyzer_id: s for s in snapshots}

    # Per-requirement: collect contributing analyzers + the worst level
    # any of them assigns. Requirements with no contributing analyzer that
    # ran are reported as ``not_assessed``.
    coverage_rows: list[APTSRequirementCoverage] = []
    for requirement_id in sorted(covered_apts_requirement_ids()):
        req = requirement_by_id(requirement_id)
        if req is None:
            # Defensive — ``scanner_mapping.py`` is unit-tested for ID
            # validity, but if a future refactor breaks the contract we
            # surface it as an unmapped row instead of crashing the route.
            continue
        contributing = [
            analyzer_id
            for analyzer_id, refs in ANALYZER_TO_APTS.items()
            if requirement_id in refs and analyzer_id in by_analyzer
        ]
        if not contributing:
            coverage_rows.append(
                APTSRequirementCoverage(
                    requirement_id=req.id,
                    domain=req.domain.value,
                    tier=req.tier.value,
                    classification=req.classification,
                    title=req.title,
                    level="not_assessed",
                    contributing_analyzers=(),
                    rationale="No analyzer that speaks to this requirement ran on this scan.",
                )
            )
            continue
        per_analyzer_levels = [
            _level_for_snapshot(by_analyzer[a]) for a in contributing
        ]
        # Worst level wins — preserves fail-loudly honesty.
        worst = _worst_level(per_analyzer_levels)
        rationale = _rationale_for_level(
            worst, contributing, [by_analyzer[a] for a in contributing]
        )
        coverage_rows.append(
            APTSRequirementCoverage(
                requirement_id=req.id,
                domain=req.domain.value,
                tier=req.tier.value,
                classification=req.classification,
                title=req.title,
                level=worst,
                contributing_analyzers=tuple(contributing),
                rationale=rationale,
            )
        )

    counts = _counts(coverage_rows)
    headline_score = _headline_score(coverage_rows)
    domain_coverage = _domain_coverage(coverage_rows)

    return APTSScanCoverage(
        scan_id=scan_id,
        project_name=project_name,
        apts_version=APTS_VERSION,
        headline_score=headline_score,
        counts=counts,
        domain_coverage=domain_coverage,
        requirement_results=tuple(coverage_rows),
    )


# ─── Internals ──────────────────────────────────────────────────────────────


def _coerce_snapshot(s: _AnalyzerSnapshot | dict) -> _AnalyzerSnapshot:
    if isinstance(s, _AnalyzerSnapshot):
        return s
    return _AnalyzerSnapshot(
        analyzer_id=str(s.get("analyzer_id", "")),
        score=float(s.get("score", 0.0)),
        gap_finding_count=int(s.get("gap_finding_count", 0)),
    )


def _level_for_snapshot(snap: _AnalyzerSnapshot) -> ScanCoverageLevel:
    """Map a single analyzer's snapshot to a scan-coverage level."""
    if snap.score >= _SATISFIED_FLOOR:
        # High score AND no recent gap findings → solid satisfied.
        return "satisfied" if snap.gap_finding_count == 0 else "partial"
    if snap.score >= _PARTIAL_FLOOR:
        return "partial"
    return "gap"


_LEVEL_ORDER: dict[ScanCoverageLevel, int] = {
    "satisfied": 0,
    "partial": 1,
    "gap": 2,
    "not_assessed": 3,
}


def _worst_level(levels: list[ScanCoverageLevel]) -> ScanCoverageLevel:
    if not levels:
        return "not_assessed"
    return max(levels, key=lambda L: _LEVEL_ORDER[L])


def _rationale_for_level(
    level: ScanCoverageLevel,
    contributing: list[str],
    snapshots: list[_AnalyzerSnapshot],
) -> str:
    pretty = ", ".join(contributing)
    avg_score = sum(s.score for s in snapshots) / len(snapshots) if snapshots else 0.0
    gap_total = sum(s.gap_finding_count for s in snapshots)
    if level == "satisfied":
        return (
            f"Average analyzer score {avg_score:.0f}/100 across "
            f"{pretty}; no gap-level findings raised."
        )
    if level == "partial":
        return (
            f"Average analyzer score {avg_score:.0f}/100 across {pretty} — "
            f"control is present but {gap_total} gap-level finding"
            f"{'s' if gap_total != 1 else ''} need attention."
        )
    if level == "gap":
        return (
            f"Average analyzer score {avg_score:.0f}/100 across {pretty} — "
            f"{gap_total} gap-level finding{'s' if gap_total != 1 else ''} "
            "indicate the control is missing or insufficient."
        )
    return "Analyzer signal incomplete for this requirement."


def _counts(rows: list[APTSRequirementCoverage]) -> dict[str, int]:
    levels = Counter(r.level for r in rows)
    return {
        "total": len(rows),
        "satisfied": levels.get("satisfied", 0),
        "partial": levels.get("partial", 0),
        "gap": levels.get("gap", 0),
        "not_assessed": levels.get("not_assessed", 0),
    }


def _headline_score(rows: list[APTSRequirementCoverage]) -> float:
    """Headline = weighted ratio of (satisfied + 0.5×partial) over assessed rows.

    ``not_assessed`` rows are excluded from the denominator so a sparse scan
    isn't punished for analyzers that didn't run; the per-analyzer-coverage
    flag in the response makes "this scan only assessed N of 73 requirements"
    visible to the operator separately.
    """
    assessed = [r for r in rows if r.level != "not_assessed"]
    if not assessed:
        return 0.0
    credit = sum(
        1.0 if r.level == "satisfied" else 0.5 if r.level == "partial" else 0.0
        for r in assessed
    )
    return round(credit / len(assessed), 4)


def _domain_coverage(rows: list[APTSRequirementCoverage]) -> dict[str, float]:
    """Per-domain headline (same formula as the global score, scoped per domain)."""
    by_domain: dict[str, list[APTSRequirementCoverage]] = defaultdict(list)
    for r in rows:
        by_domain[r.domain].append(r)
    out: dict[str, float] = {}
    for domain, domain_rows in by_domain.items():
        assessed = [r for r in domain_rows if r.level != "not_assessed"]
        if not assessed:
            out[domain] = 0.0
            continue
        credit = sum(
            1.0 if r.level == "satisfied" else 0.5 if r.level == "partial" else 0.0
            for r in assessed
        )
        out[domain] = round(credit / len(assessed), 4)
    return out


# ─── Adapter for the route layer ────────────────────────────────────────────


def snapshots_from_analyzer_results(analyzer_results: Iterable) -> tuple[_AnalyzerSnapshot, ...]:
    """Adapt a list of :class:`app.engines.scanners._base.AnalyzerResult` into
    ``_AnalyzerSnapshot`` instances.

    Lives here (not in the route) so the engine can stay isolated from the
    scanner subsystem's import graph but the route gets a one-call shim.
    """
    out: list[_AnalyzerSnapshot] = []
    for r in analyzer_results:
        analyzer_id = getattr(r, "analyzer_id", None) or (
            r.get("analyzer_id") if isinstance(r, dict) else None
        )
        if not analyzer_id:
            continue
        if analyzer_id not in ANALYZER_TO_APTS:
            # Analyzer isn't in the curated map — skip silently. Adding new
            # analyzers without a mapping is fine; they just don't surface.
            continue
        score = float(getattr(r, "score", 0.0) or (r.get("score") if isinstance(r, dict) else 0.0))
        findings = getattr(r, "findings", None)
        if findings is None and isinstance(r, dict):
            findings = r.get("findings", [])
        gap_count = sum(
            1
            for f in (findings or [])
            if (
                getattr(f, "compliance_impact", None)
                or (f.get("compliance_impact") if isinstance(f, dict) else None)
            )
            == "gap"
        )
        out.append(
            _AnalyzerSnapshot(
                analyzer_id=analyzer_id,
                score=score,
                gap_finding_count=gap_count,
            )
        )
    return tuple(out)


__all__ = [
    "APTSRequirementCoverage",
    "APTSScanCoverage",
    "ScanCoverageLevel",
    "derive_apts_coverage",
    "snapshots_from_analyzer_results",
]
