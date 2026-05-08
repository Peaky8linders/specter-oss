"""OWASP APTS (Autonomous Penetration Testing Standard) integration.

OWASP APTS v0.1.0 is a governance standard, not a runnable scanner — 173
requirements across 8 domains (Scope Enforcement, Safety Controls, Human
Oversight, Graduated Autonomy, Auditability, Manipulation Resistance, Supply
Chain Trust, Reporting) split into three compliance tiers (Foundation,
Verified, Comprehensive). The standard governs *autonomous* pentesting
platforms — exactly the shape of the antifragile-ai live-attack + three-agent
verifier surface this product already ships.

This module makes APTS a first-class citizen in the Cybersec Agents Hub by:

1. Vendoring the canonical machine-readable requirements catalog
   (CC BY-SA 4.0, attributed to OWASP) so the engine can run offline + in
   air-gapped customer deployments.
2. Carrying a hand-curated evidence map from each requirement ID to the
   platform module that demonstrably implements it (or a structured GAP /
   PARTIAL marker so an auditor sees exactly where the platform stops).
3. Producing a structured ``ConformanceReport`` per assessed system: tier
   readiness (Tier 1 / 2 / 3 hits), per-domain coverage, MUST vs SHOULD
   completion, and per-requirement evidence pointers.
4. Exposing the report through ``/api/v1/apts/*`` so the frontend Cybersec
   Agents Hub can surface APTS as the **default scanner** for any AI system
   that already has a security campaign or audit row.

The integration is read-only against the standard — we never mutate the
vendored JSON. Updating the standard is a documented quarterly chore
(``scripts/_refresh_apts_standard.py``) that re-fetches from the upstream
OWASP/APTS repo and re-runs the conformance test fixture.
"""

from specter.apts.conformance import (
    ConformanceLevel,
    ConformanceReport,
    DomainSummary,
    RequirementResult,
    TierStatus,
    assess_self,
    assess_target,
)
from specter.apts.evidence_map import (
    EvidenceClaim,
    get_evidence_map,
)
from specter.apts.models import (
    APTSDomain,
    APTSRequirement,
    APTSTier,
)
from specter.apts.requirements import (
    APTS_VERSION,
    list_domains,
    load_requirements,
    requirement_by_id,
    requirements_by_domain,
    requirements_by_tier,
)
from specter.apts.scanner_coverage import (
    APTSRequirementCoverage,
    APTSScanCoverage,
    ScanCoverageLevel,
    derive_apts_coverage,
    snapshots_from_analyzer_results,
)
from specter.apts.scanner_mapping import (
    ANALYZER_TO_APTS,
    analyzers_for_apts_requirement,
    apts_requirements_for_analyzer,
    covered_apts_requirement_ids,
)

__all__ = [
    "ANALYZER_TO_APTS",
    "APTS_VERSION",
    "APTSDomain",
    "APTSRequirement",
    "APTSRequirementCoverage",
    "APTSScanCoverage",
    "APTSTier",
    "ConformanceLevel",
    "ConformanceReport",
    "DomainSummary",
    "EvidenceClaim",
    "RequirementResult",
    "ScanCoverageLevel",
    "TierStatus",
    "analyzers_for_apts_requirement",
    "apts_requirements_for_analyzer",
    "assess_self",
    "assess_target",
    "covered_apts_requirement_ids",
    "derive_apts_coverage",
    "get_evidence_map",
    "list_domains",
    "load_requirements",
    "requirement_by_id",
    "requirements_by_domain",
    "requirements_by_tier",
    "snapshots_from_analyzer_results",
]
