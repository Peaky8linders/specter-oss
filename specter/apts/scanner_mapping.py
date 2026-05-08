"""Curated mapping: Code Scanner analyzer → APTS requirement IDs.

The 21 analyzers in ``vendor/specter/engines/scanners/__init__.py`` evaluate the same
categories of risk that OWASP APTS asks of autonomous pentesting platforms.
This map records, per analyzer, which APTS requirements that analyzer can
*speak to* — i.e. its findings (positive / neutral / gap) are evidence one
way or the other on those requirements.

Adding an entry requires the requirement id to exist in the vendored
catalog (``apts_requirements.json``); a unit test enforces this so a
typo or stale id can't ship. Removing an analyzer is fine — its row simply
drops out of the per-scan coverage report.

Mapping principles:

* **Honest**: each edge represents a control the analyzer ACTUALLY checks.
  We never claim coverage for a requirement the analyzer can't see.
* **Narrow**: an analyzer may legitimately speak to 2-6 requirements; if
  the list grows past that the analyzer's findings are too diffuse to
  yield a useful per-requirement signal.
* **Stable**: adding new analyzers later won't break existing edges. The
  coverage engine treats unmapped analyzers as silent (they contribute
  nothing) instead of erroring.
"""

from __future__ import annotations

from types import MappingProxyType


# Per-analyzer list of APTS requirement IDs the analyzer's findings illuminate.
# IDs follow the canonical APTS-XX-NNN form; the unit test
# ``TestScannerMappingIntegrity`` asserts every id resolves through
# ``app.integrations.apts.requirements.requirement_by_id``.
_RAW_ANALYZER_TO_APTS: dict[str, tuple[str, ...]] = {
    # ── Baseline analyzers (14) ─────────────────────────────────────────────
    "ai_frameworks": (
        # Framework + library + version pinning is the closest analogue to
        # APTS's foundation-model + provenance posture.
        "APTS-TP-002",  # Model version pinning + change management
        "APTS-TP-019",  # AI model provenance + training data governance
        "APTS-TP-021",  # Foundation model disclosure + capability baseline
    ),
    "data_pipeline": (
        # Data classification + sensitive-data handling on the ingestion path.
        "APTS-AR-015",  # Evidence classification + sensitive data handling
        "APTS-TP-012",  # Client data classification framework
        "APTS-TP-013",  # Sensitive data discovery + handling
    ),
    "human_oversight": (
        # Pre-approval gates, real-time monitoring, and the gate before
        # irreversible actions are the textbook APTS-HO surface.
        "APTS-HO-001",  # Mandatory pre-approval gates for L1/L2 autonomy
        "APTS-HO-002",  # Real-time monitoring + intervention capability
        "APTS-HO-010",  # Human decision before irreversible actions
        "APTS-RP-002",  # Finding verification + human review pipeline
    ),
    "security_controls": (
        # Impact classification + rate limiting + action allowlist + boundary
        # enforcement — the four pillars APTS-SC + APTS-MR ask for.
        "APTS-SC-001",  # Impact classification + CIA scoring
        "APTS-SC-004",  # Rate limiting, bandwidth, and payload constraints
        "APTS-SC-020",  # Action allowlist enforcement external to the model
        "APTS-MR-001",  # Instruction boundary enforcement
        "APTS-MR-002",  # Response validation + sanitization
    ),
    "fairness_testing": (
        # Fairness + bias testing maps onto APTS's reporting-quality controls
        # (FP/FN rate disclosure) more than any other domain.
        "APTS-RP-006",  # False positive rate disclosure
        "APTS-RP-009",  # False negative rate disclosure + methodology
    ),
    "test_suite": (
        # Test suite presence is the foundation of safety-control regression
        # testing — APTS's "did you re-run safety controls after platform
        # updates" check.
        "APTS-AR-017",  # Safety control regression testing after updates
    ),
    "logging_monitoring": (
        # Structured logging + state transitions + cryptographic hashing
        # are the canonical APTS-AR-001/002/010 trio.
        "APTS-AR-001",  # Structured event logging with schema validation
        "APTS-AR-002",  # State transition logging
        "APTS-AR-010",  # Cryptographic hashing of all evidence
        "APTS-AR-012",  # Tamper-evident logging with hash chains
    ),
    "documentation": (
        # Docs presence + transparency-report quality.
        "APTS-AR-009",  # Transparency report requirements
        "APTS-RP-011",  # Executive summary + risk overview
        "APTS-TP-021",  # Foundation model disclosure + capability baseline
    ),
    "configuration": (
        # Config-file integrity + credential lifecycle posture.
        "APTS-MR-004",  # Configuration file integrity verification
        "APTS-SE-023",  # Credential and secret lifecycle governance
        "APTS-TP-014",  # Data encryption + cryptographic controls
    ),
    "agent_cascade": (
        # Multi-step + automatic chaining + boundary monitoring during
        # automated chains — the heart of APTS-AL graduated autonomy.
        "APTS-AL-007",  # Multi-step technique chaining within single phase
        "APTS-AL-013",  # Complete attack chain execution within boundaries
        "APTS-AL-016",  # Continuous boundary monitoring + breach detection
        "APTS-SE-026",  # Out-of-distribution action monitoring
    ),
    "lethal_trifecta": (
        # AEPD rule-of-2 architecture: untrusted-input + sensitive-data +
        # outbound-action. APTS calls these out as MR-009/011/018.
        "APTS-MR-009",  # SSRF prevention in testing
        "APTS-MR-011",  # Out-of-band communication prevention
        "APTS-MR-018",  # AI model input/output architectural boundary
    ),
    "adversarial_robustness": (
        # Adversarial-example detection + resilience testing.
        "APTS-MR-013",  # Adversarial example detection in vuln classification
        "APTS-MR-020",  # Adversarial validation + resilience testing
        "APTS-RP-007",  # Independent finding reproducibility
    ),
    "terraform": (
        # Terraform IaC analyzer covers cloud-native + ephemeral infra
        # governance + cloud security configuration.
        "APTS-SE-024",  # Cloud-native + ephemeral infrastructure governance
        "APTS-TP-008",  # Cloud security configuration + hardening
    ),
    "cloudformation_k8s": (
        # CloudFormation + Kubernetes — same APTS surface as Terraform plus
        # multi-tenant engagement isolation when Kubernetes namespaces drive it.
        "APTS-SE-024",  # Cloud-native + ephemeral infrastructure governance
        "APTS-TP-008",  # Cloud security configuration + hardening
        "APTS-TP-017",  # Multi-tenant + engagement isolation
    ),
    "cicd_dockerfile": (
        # CI/CD pipeline + Dockerfile analyzer hits deployment-triggered
        # testing governance + supply chain attestation.
        "APTS-SE-020",  # Deployment-triggered testing governance
        "APTS-AR-016",  # Platform integrity + supply chain attestation
        "APTS-TP-006",  # Dependency inventory + risk + supply chain
    ),
    "cloud_deployment": (
        # Generic cloud-deployment analyzer — same supply-chain + cloud-config
        # surface as Terraform / CloudFormation / Kubernetes.
        "APTS-SE-024",  # Cloud-native + ephemeral infrastructure governance
        "APTS-TP-008",  # Cloud security configuration + hardening
        "APTS-TP-007",  # Data residency and sovereignty
    ),
    "model_typology": (
        # Model classification + typology maps to foundation-model disclosure.
        "APTS-TP-019",  # AI model provenance + training data governance
        "APTS-TP-021",  # Foundation model disclosure + capability baseline
        "APTS-TP-022",  # Re-attestation on material model change
    ),

    # ── Agent-aware analyzers (Nannini et al. 2026, 7) ──────────────────────
    "agent_inventory": (
        # External-action inventory + asset criticality classification —
        # the "what does the agent actually do" surface.
        "APTS-SE-001",  # Rules of Engagement specification + validation
        "APTS-SE-005",  # Asset criticality classification + integration
        "APTS-AR-008",  # Context-aware decision logging
    ),
    "privilege_minimization": (
        # Privilege-on-the-LLM-prompt antipattern + tool-permission registry
        # → action allowlist + credential lifecycle.
        "APTS-SC-020",  # Action allowlist enforcement external to the model
        "APTS-SE-023",  # Credential + secret lifecycle governance
        "APTS-MR-019",  # Discovered credential protection
    ),
    "runtime_drift": (
        # Floating model aliases + inline system prompts + drift detection
        # → APTS-AR-019 + APTS-SE-007 + APTS-TP-022.
        "APTS-AR-019",  # AI/ML model change tracking + drift detection
        "APTS-SE-007",  # Dynamic scope monitoring + drift detection
        "APTS-TP-022",  # Re-attestation on material foundation model change
    ),
    "regulatory_perimeter": (
        # Regulatory-perimeter inventory drives pre-action validation +
        # legal/compliance escalation triggers.
        "APTS-SE-006",  # Pre-action scope validation
        "APTS-HO-014",  # Legal + compliance escalation triggers
    ),
}


# Read-only frozen mapping so callers can't accidentally mutate the
# curated map at runtime. ``MappingProxyType`` is the standard idiom.
ANALYZER_TO_APTS: MappingProxyType[str, tuple[str, ...]] = MappingProxyType(
    {analyzer_id: refs for analyzer_id, refs in _RAW_ANALYZER_TO_APTS.items()}
)


def apts_requirements_for_analyzer(analyzer_id: str) -> tuple[str, ...]:
    """Return APTS requirement IDs the named analyzer can speak to."""
    return ANALYZER_TO_APTS.get(analyzer_id, ())


def analyzers_for_apts_requirement(requirement_id: str) -> tuple[str, ...]:
    """Inverse lookup: which analyzers contribute evidence on this requirement."""
    return tuple(
        analyzer_id
        for analyzer_id, refs in ANALYZER_TO_APTS.items()
        if requirement_id in refs
    )


def covered_apts_requirement_ids() -> frozenset[str]:
    """The full set of APTS requirement IDs the scanner network can touch."""
    return frozenset(req for refs in ANALYZER_TO_APTS.values() for req in refs)
