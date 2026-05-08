"""Pydantic v2 models for the OWASP APTS integration.

Mirrors the upstream ``apts_requirements_schema.json`` field set verbatim,
plus an enum-typed ``domain`` and ``tier`` so downstream code can branch
without string comparisons. Adding fields here is fine; renaming or
removing them is a breaking change because the report's ``source_row_hash``
participates in the evidence chain.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APTSDomain(str, Enum):
    """The 8 APTS conformance domains.

    String values match the upstream JSON schema verbatim so deserialisation
    is one-to-one — never paraphrase these labels.
    """

    scope_enforcement = "Scope Enforcement"
    safety_controls = "Safety Controls"
    human_oversight = "Human Oversight"
    graduated_autonomy = "Graduated Autonomy"
    auditability = "Auditability"
    manipulation_resistance = "Manipulation Resistance"
    supply_chain_trust = "Supply Chain Trust"
    reporting = "Reporting"


# Stable per-domain prefix, matches APTS-XX-NNN ID format.
DOMAIN_PREFIX: dict[APTSDomain, str] = {
    APTSDomain.scope_enforcement: "SE",
    APTSDomain.safety_controls: "SC",
    APTSDomain.human_oversight: "HO",
    APTSDomain.graduated_autonomy: "AL",
    APTSDomain.auditability: "AR",
    APTSDomain.manipulation_resistance: "MR",
    APTSDomain.supply_chain_trust: "TP",
    APTSDomain.reporting: "RP",
}


class APTSTier(int, Enum):
    """The three APTS conformance tiers.

    * Tier 1 (Foundation) — 72 requirements. The platform won't test outside
      scope, can be stopped immediately, and provides an audit trail.
    * Tier 2 (Verified) — 85 additional (157 cumulative). Full transparency,
      tamper-proof audit trails, independently verifiable findings.
    * Tier 3 (Comprehensive) — 16 additional (173 cumulative). Highest
      assurance for critical infrastructure + L4 autonomous operations.
    """

    foundation = 1
    verified = 2
    comprehensive = 3


class APTSRequirement(BaseModel):
    """One row from the vendored ``apts_requirements.json`` catalog."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=r"^APTS-[A-Z]+-\d+$", min_length=10, max_length=24)
    domain: APTSDomain
    tier: APTSTier
    classification: Literal["MUST", "SHOULD"]
    title: str = Field(..., min_length=1, max_length=512)
