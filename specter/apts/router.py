"""OWASP APTS conformance routes (FastAPI).

Six surfaces:

* ``GET  /apts/manifest`` — vendored catalog version + license + URL.
* ``GET  /apts/requirements`` — filterable list of all 173.
* ``GET  /apts/requirements/{requirement_id}`` — single requirement.
* ``GET  /apts/domains`` — eight canonical domains + per-domain count.
* ``GET  /apts/conformance/self`` — platform self-conformance against
  the curated evidence map.
* ``GET  /apts/conformance/system/{target_id}`` — target-anchored
  conformance (caller wires their own auth on this one).

All routes are pure-functional reads against the vendored standard
catalog + the Python-side evidence map. Hosts that want
audit-chain persistence can wrap ``conformance_for_system`` with their
own dependency-injection layer.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from specter.apts.conformance import (
    ConformanceReport,
    DomainSummary,
    RequirementResult,
    TierStatus,
    assess_self,
    assess_target,
)
from specter.apts.models import APTSDomain
from specter.apts.requirements import (
    list_domains,
    load_requirements,
    requirement_by_id,
    requirements_by_domain,
)
from specter.apts.requirements import (
    manifest as apts_manifest,
)

apts_router = APIRouter(tags=["apts"])


# ─── Catalog (public) ───────────────────────────────────────────────────────


@apts_router.get(
    "/apts/manifest",
    summary="OWASP APTS catalog manifest — version + license + source.",
)
async def get_manifest(request: Request) -> dict[str, Any]:
    return apts_manifest()


@apts_router.get(
    "/apts/requirements",
    summary="List APTS requirements; filterable by domain + tier + classification.",
)
async def list_requirements(
    request: Request,
    domain: APTSDomain | None = Query(
        default=None,
        description="Filter by canonical domain label.",
    ),
    tier: int | None = Query(default=None, ge=1, le=3, description="Filter by tier 1/2/3."),
    classification: str | None = Query(
        default=None,
        pattern="^(MUST|SHOULD)$",
        description="Filter by classification; MUST or SHOULD.",
    ),
) -> list[dict[str, Any]]:
    rows = load_requirements()
    if domain is not None:
        rows = tuple(r for r in rows if r.domain == domain)
    if tier is not None:
        rows = tuple(r for r in rows if r.tier.value == tier)
    if classification is not None:
        rows = tuple(r for r in rows if r.classification == classification)
    return [r.model_dump(mode="json") for r in rows]


@apts_router.get(
    "/apts/requirements/{requirement_id}",
    summary="Single APTS requirement by id (e.g. APTS-SE-001).",
)
async def get_requirement(
    request: Request,
    requirement_id: str,
) -> dict[str, Any]:
    req = requirement_by_id(requirement_id)
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "apts_requirement_not_found",
                "message": f"No APTS requirement with id {requirement_id!r}.",
            },
        )
    return req.model_dump(mode="json")


@apts_router.get(
    "/apts/domains",
    summary="Eight APTS conformance domains with per-domain count.",
)
async def get_domains(request: Request) -> list[dict[str, Any]]:
    return [
        {
            "domain": d.value,
            "count": len(requirements_by_domain(d)),
        }
        for d in list_domains()
    ]


# ─── Conformance ────────────────────────────────────────────────────────────


def _serialize_report(report: ConformanceReport) -> dict[str, Any]:
    """Stable JSON shape used by both /self and /system endpoints."""
    return {
        "target_id": report.target_id,
        "target_label": report.target_label,
        "apts_version": report.apts_version,
        "generated_at": report.generated_at.isoformat(),
        "headline_score": report.headline_score,
        "headline_tier": report.headline_tier.value if report.headline_tier else None,
        "counts": report.counts,
        "tier_status": [_tier_dict(t) for t in report.tier_status],
        "domain_summaries": [_domain_dict(d) for d in report.domain_summaries],
        "requirement_results": [_result_dict(r) for r in report.requirement_results],
    }


def _tier_dict(t: TierStatus) -> dict[str, Any]:
    return {
        "tier": t.tier.value,
        "label": t.label,
        "achieved": t.achieved,
        "must_total": t.must_total,
        "must_satisfied": t.must_satisfied,
        "must_partial": t.must_partial,
        "must_gap": t.must_gap,
        "should_total": t.should_total,
        "should_satisfied": t.should_satisfied,
        "should_partial": t.should_partial,
        "should_gap": t.should_gap,
        "coverage_score": t.coverage_score,
    }


def _domain_dict(d: DomainSummary) -> dict[str, Any]:
    return {
        "domain": d.domain.value,
        "total": d.total,
        "satisfied": d.satisfied,
        "partial": d.partial,
        "gap": d.gap,
        "unmapped": d.unmapped,
        "must_satisfied": d.must_satisfied,
        "must_total": d.must_total,
        "coverage_score": d.coverage_score,
    }


def _result_dict(r: RequirementResult) -> dict[str, Any]:
    return {
        "requirement_id": r.requirement_id,
        "domain": r.domain.value,
        "tier": r.tier.value,
        "classification": r.classification,
        "title": r.title,
        "level": r.level,
        "rationale": r.rationale,
        "modules": list(r.modules),
        "test_anchors": list(r.test_anchors),
        "article_anchors": list(r.article_anchors),
    }


@apts_router.get(
    "/apts/conformance/self",
    summary="Platform self-conformance assessment (curated evidence map).",
)
async def conformance_self(request: Request) -> dict[str, Any]:
    """Public APTS conformance scorecard for the platform itself.

    Pure read — repeated calls return identical results modulo
    ``generated_at``.
    """
    report = assess_self()
    return _serialize_report(report)


@apts_router.get(
    "/apts/conformance/system/{target_id}",
    summary="APTS conformance scorecard anchored to a target id.",
)
async def conformance_for_system(
    request: Request,
    target_id: str,
) -> dict[str, Any]:
    """Per-target APTS conformance.

    Re-uses the platform's curated evidence map (the target inherits
    the platform's conformance posture by default). Callers that want
    auth + audit-chain persistence wrap this route in their own
    FastAPI dependency layer.
    """
    if not target_id or len(target_id) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_target_id"},
        )

    report = assess_target(
        target_id=target_id,
        target_label=f"system:{target_id}",
    )
    return _serialize_report(report)
