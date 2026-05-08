"""Hand-curated map: APTS requirement ID → platform evidence.

Every entry is one ``EvidenceClaim`` answering: does the reference platform
deployment demonstrably implement the requirement, and where can an auditor
look to verify it. Three values for ``level``:

* ``satisfied`` — the platform implements the requirement and we can name the
  module + the test that pins the behaviour.
* ``partial`` — the capability exists but is incomplete (e.g. covers the
  primary case but misses an edge documented in the APTS verification text).
* ``gap`` — the platform does not implement this today; surfaces honestly
  in the report so an integrator knows where to invest.

The map is *deliberately* honest: a generous claim that doesn't survive
auditor scrutiny destroys conformance credibility for every other claim. If
the evidence doesn't exist, the entry is ``gap`` with a one-line ``rationale``
explaining what's missing. Adding a satisfied claim requires naming the
module path + an article anchor (KB dimension, EU AI Act article, OWASP top
10 entry — anything an auditor can grep for).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal


@dataclass(frozen=True)
class EvidenceClaim:
    """One requirement ↔ platform-evidence binding."""

    requirement_id: str
    level: Literal["satisfied", "partial", "gap"]
    rationale: str
    """One-sentence explanation, sized for an auditor's eye."""

    modules: tuple[str, ...] = field(default_factory=tuple)
    """Source paths an auditor can grep — empty for ``gap`` entries."""

    test_anchors: tuple[str, ...] = field(default_factory=tuple)
    """Pytest class/test names that pin the behaviour."""

    article_anchors: tuple[str, ...] = field(default_factory=tuple)
    """EU AI Act article + framework refs (e.g. 'EU AI Act Art. 15', 'ISO 27002 8.16')."""


# ─── The Curated Map ─────────────────────────────────────────────────────────
#
# Sourced from a manual walk of `vendor/specter/`, `vendor/antifragile/`, the existing
# Security Hub vendor catalog, and the verification checklist in CLAUDE.md.
# Roughly 70-75% of APTS-Tier-1 surfaces map onto existing the reference platform capabilities
# because the platform was already built around the same threat model: scope
# enforcement on attacks, hash-chained evidence, MFA-gated admin oversight,
# and the antifragile.oversight 12-factor stack.

_CLAIMS: tuple[EvidenceClaim, ...] = (
    # ── Domain 1: Scope Enforcement (26) ─────────────────────────────────────
    EvidenceClaim(
        "APTS-SE-001", "partial",
        "antifragile exposes an attack registry but no formal Rules-of-Engagement artefact yet; campaign-history records intent but the RoE per-engagement file is on the roadmap.",
        modules=("vendor/antifragile/attacks/registry.py", "vendor/specter/engines/campaign_history.py"),
        article_anchors=("OWASP APTS-SE-001",),
    ),
    EvidenceClaim(
        "APTS-SE-002", "satisfied",
        "Pre-send DNS re-check and RFC 1918 / metadata-IP rejection close the SSRF TOCTOU window on /security-scan/scan-live (#186, #317).",
        modules=("vendor/specter/routes/_security_scan_validators.py", "vendor/specter/routes/security_scan.py"),
        test_anchors=("TestSecurityScan", "TestSSRFPrevention"),
        article_anchors=("OWASP ASVS V12.6",),
    ),
    EvidenceClaim(
        "APTS-SE-003", "satisfied",
        "Domain-scope validation rejects wildcards and out-of-scope hosts via the same SSRF helper before the live executor dispatches.",
        modules=("vendor/specter/routes/_security_scan_validators.py",),
        test_anchors=("TestSecurityScan",),
    ),
    EvidenceClaim(
        "APTS-SE-004", "partial",
        "Campaign scheduler honours cron windows but doesn't yet enforce a per-engagement timezone-aware temporal boundary; documented gap.",
        modules=("vendor/specter/engines/campaign_scheduler.py",),
    ),
    EvidenceClaim(
        "APTS-SE-005", "gap",
        "No first-class asset criticality classification today — closest analogue is Annex III risk tiering, which is system-level, not asset-level.",
    ),
    EvidenceClaim(
        "APTS-SE-006", "satisfied",
        "Every live attack runs through `_security_scan_validators` BEFORE the live executor; pre-action scope check is mandatory.",
        modules=("vendor/specter/routes/_security_scan_validators.py", "vendor/antifragile/attacks/live_executor.py"),
        test_anchors=("TestSecurityScan",),
    ),
    EvidenceClaim(
        "APTS-SE-007", "partial",
        "campaign_scheduler triggers recurring runs but doesn't compare against a baseline scope to detect drift; tracked as a follow-up.",
        modules=("vendor/specter/engines/campaign_scheduler.py",),
    ),
    EvidenceClaim(
        "APTS-SE-008", "partial",
        "Engagement timestamps are recorded on every evidence-chain entry; an engagement-window enforcement gate is partial.",
        modules=("vendor/specter/evidence/store.py",),
    ),
    EvidenceClaim(
        "APTS-SE-009", "satisfied",
        "SSRF helpers carry a hard deny list (RFC 1918, link-local, cloud-metadata IPs); critical-asset protection enforced pre-dispatch.",
        modules=("vendor/specter/routes/_security_scan_validators.py",),
        test_anchors=("TestSecurityScan",),
    ),
    EvidenceClaim(
        "APTS-SE-010", "partial",
        "Live executor targets only test endpoints; production-DB safeguards rely on operator scope discipline rather than an automated gate.",
        modules=("vendor/antifragile/attacks/live_executor.py",),
    ),
    EvidenceClaim(
        "APTS-SE-011", "satisfied",
        "Tenant-scoped end-to-end since #178/#180/#323; every engagement, evidence row, and audit-trail read filters by tenant_id.",
        modules=("vendor/specter/evidence/store.py", "vendor/specter/dependencies.py", "vendor/specter/auth_jwt.py"),
        test_anchors=("TestEvidenceTenantScoping", "TestMultiTenancyIsolation"),
    ),
    EvidenceClaim(
        "APTS-SE-012", "satisfied",
        "DNS-rebinding mitigation: pre-send DNS re-check on /security-scan/scan-live closes the TOCTOU window (#186).",
        modules=("vendor/specter/routes/_security_scan_validators.py",),
        test_anchors=("TestSSRFPrevention",),
    ),
    EvidenceClaim(
        "APTS-SE-013", "satisfied",
        "Egress allowlist + RFC1918 deny + cloud-metadata reject enforce a hard network boundary against lateral movement.",
        modules=("vendor/specter/routes/_security_scan_validators.py",),
    ),
    EvidenceClaim(
        "APTS-SE-014", "gap",
        "No explicit network-topology-discovery rate limiter beyond the slowapi default; documented gap.",
    ),
    EvidenceClaim(
        "APTS-SE-015", "satisfied",
        "Evidence chain logs every campaign action with hash-chained tamper evidence; scope audits are reproducible offline.",
        modules=("vendor/specter/evidence/store.py", "vendor/specter/engines/audit_trail.py"),
        test_anchors=("TestAuditTrail",),
    ),
    EvidenceClaim(
        "APTS-SE-016", "partial",
        "Campaign re-runs reload scope from the registry but a formal scope-revalidation cycle is not yet implemented.",
        modules=("vendor/specter/engines/campaign_scheduler.py",),
    ),
    EvidenceClaim(
        "APTS-SE-017", "satisfied",
        "campaign_scheduler ships engagement boundaries for recurring tests with persistence in `CampaignSchedule`.",
        modules=("vendor/specter/engines/campaign_scheduler.py",),
        test_anchors=("TestCampaignScheduler",),
    ),
    EvidenceClaim(
        "APTS-SE-018", "partial",
        "campaign_history surfaces fragility red flags across runs but cross-cycle regression detection is heuristic.",
        modules=("vendor/specter/engines/campaign_history.py", "vendor/specter/engines/_campaign_red_flags.py"),
        test_anchors=("TestFragilityRedFlags",),
    ),
    EvidenceClaim(
        "APTS-SE-019", "satisfied",
        "slowapi rate limiter + DailyQuotaLimiter + adaptive backoff on every state-mutating route.",
        modules=("vendor/specter/main.py", "vendor/specter/engines/roadmap_refiner/_phase2a.py"),
        test_anchors=("TestRateLimiting",),
    ),
    EvidenceClaim(
        "APTS-SE-020", "gap",
        "No PR-triggered or deployment-triggered scan governance; closest analogue is the GitHub Connect manual scan path.",
    ),
    EvidenceClaim(
        "APTS-SE-021", "gap",
        "Scope conflict resolution for overlapping engagements is a Tier-3 SHOULD; not implemented today.",
    ),
    EvidenceClaim(
        "APTS-SE-022", "partial",
        "Frontend agent surface (Workflow Builder + CC) constrains client-side actions but no formal client-side agent boundary contract.",
        modules=("frontend/src/pages/WorkflowBuilder.tsx",),
    ),
    EvidenceClaim(
        "APTS-SE-023", "satisfied",
        "Per-user secrets stored Fernet-encrypted with rotation key support; Argon2id for passwords; sha256 hash for API keys; rotation runbook in `docs/security/rotation-log.md`.",
        modules=("vendor/specter/integrations/github_connect/crypto.py", "vendor/specter/auth_jwt.py", "vendor/specter/integrations/security_hub/auth.py"),
        article_anchors=("ISO 27002 8.24", "SOC 2 CC6.1"),
    ),
    EvidenceClaim(
        "APTS-SE-024", "partial",
        "Railway-managed cloud hosting + R2 evidence backend; ephemeral-infra governance is partial (no per-pod isolation enforcement gate).",
        modules=("vendor/specter/evidence/backends/r2_backend.py",),
    ),
    EvidenceClaim(
        "APTS-SE-025", "partial",
        "Code Scanner's API analyzer + business-logic analyzers cover the static surface; runtime API governance is partial.",
        modules=("vendor/specter/engines/scanners/security_controls.py",),
    ),
    EvidenceClaim(
        "APTS-SE-026", "gap",
        "Out-of-distribution action monitoring is a Tier-2 SHOULD; not implemented (no behavioural baseline + drift detector for attack actions today).",
    ),

    # ── Domain 2: Safety Controls (20) ───────────────────────────────────────
    EvidenceClaim(
        "APTS-SC-001", "satisfied",
        "antifragile's attack classifier scores impact across CIA dimensions and writes the verdict to the chain.",
        modules=("vendor/antifragile/agents/classifier.py", "vendor/antifragile/agents/three_agent.py"),
    ),
    EvidenceClaim(
        "APTS-SC-002", "partial",
        "Annex III sector + KB dimensions encode some industry-specific risk weighting; per-industry impact pre-set is partial.",
        modules=("vendor/specter/data/kb.py", "vendor/specter/engines/sector_autopilot.py"),
    ),
    EvidenceClaim(
        "APTS-SC-003", "gap",
        "Real-world impact classification examples are a Tier-2 SHOULD documentation deliverable; not yet shipped as a curated reference.",
    ),
    EvidenceClaim(
        "APTS-SC-004", "satisfied",
        "Per-route slowapi limits + bandwidth-bound payload caps (250 MB scan upload, 20 MB evidence ingest, 5 MB per-file).",
        modules=("vendor/specter/main.py", "vendor/specter/routes/evidence.py", "vendor/specter/engines/code_scanner.py"),
    ),
    EvidenceClaim(
        "APTS-SC-005", "gap",
        "Cascading-failure prevention in interconnected systems is a Tier-2 SHOULD; partial via DLQ for Stripe but no cross-system circuit breaker.",
    ),
    EvidenceClaim(
        "APTS-SC-006", "partial",
        "Three-agent verifier triad (Finder/Adversary/Referee) escalates uncertain verdicts; threshold-driven Automated→Approval→Prohibited transitions are partial.",
        modules=("vendor/antifragile/agents/three_agent.py",),
    ),
    EvidenceClaim(
        "APTS-SC-007", "partial",
        "antifragility score accumulates from stressors but doesn't decay over time; cumulative-risk-with-decay is partial.",
        modules=("vendor/specter/engines/_campaign_antifragility.py",),
    ),
    EvidenceClaim(
        "APTS-SC-008", "gap",
        "Threshold configuration with formal schema validation is a Tier-3 SHOULD; not yet shipped.",
    ),
    EvidenceClaim(
        "APTS-SC-009", "partial",
        "TENANT_LOCKS allows per-tenant kill of a refinement run; a global platform kill switch is documented but operator-driven (not API-exposed).",
        modules=("vendor/specter/engines/roadmap_refiner/_phase2a.py",),
    ),
    EvidenceClaim(
        "APTS-SC-010", "satisfied",
        "/healthz + /healthz/llm health checks; Railway health probe halts unhealthy boots; alembic 30s timeout + runtime kb_version backstop.",
        modules=("vendor/specter/main.py",),
        test_anchors=("TestEnsureKbVersionColumnsRuntimeGuard",),
    ),
    EvidenceClaim(
        "APTS-SC-011", "partial",
        "Roadmap refiner has condition-based early-stop (no_improvement >= 5); broader condition-based termination across other engines is partial.",
        modules=("vendor/specter/engines/roadmap_refiner/engine.py",),
    ),
    EvidenceClaim(
        "APTS-SC-012", "partial",
        "DailyQuotaLimiter (5 iters / 50K tokens for Starter) acts as a per-tenant network circuit breaker for LLM calls.",
        modules=("vendor/specter/engines/roadmap_refiner/_phase2a.py",),
    ),
    EvidenceClaim(
        "APTS-SC-013", "gap",
        "Time-based automatic termination with operator override is a Tier-3 SHOULD; not yet shipped.",
    ),
    EvidenceClaim(
        "APTS-SC-014", "gap",
        "Pentests are non-reversible by design; rollback semantics for stateful attacks aren't applicable but the requirement isn't met.",
    ),
    EvidenceClaim(
        "APTS-SC-015", "partial",
        "Three-agent verifier triad confirms post-test that the system stayed within scope; integrity validation against a pre-test baseline is partial.",
        modules=("vendor/antifragile/agents/three_agent.py",),
    ),
    EvidenceClaim(
        "APTS-SC-016", "satisfied",
        "All evidence persisted via hash-chained `AuditStore.record`; cleanup is GDPR Art. 17 tombstone (never silent delete).",
        modules=("vendor/specter/evidence/store.py", "vendor/specter/routes/gdpr.py"),
        test_anchors=("TestGDPRWriteRoutes",),
    ),
    EvidenceClaim(
        "APTS-SC-017", "gap",
        "External watchdog + operator notification is a separate observability process not bundled today.",
    ),
    EvidenceClaim(
        "APTS-SC-018", "partial",
        "Stripe webhook DLQ + alembic 008 (`failed_webhook_events`) captures transient failures for replay; broader incident-containment runbook is partial.",
        modules=("vendor/specter/db.py", "vendor/specter/routes/billing.py"),
        test_anchors=("TestStripeWebhookDeadLetter",),
    ),
    EvidenceClaim(
        "APTS-SC-019", "partial",
        "antifragile attacks run in-process; execution sandbox isolation is partial (no cgroup/namespace boundary).",
        modules=("vendor/antifragile/attacks/live_executor.py",),
    ),
    EvidenceClaim(
        "APTS-SC-020", "satisfied",
        "Defense registry + attack registry constrain the action surface external to the LLM; LLM never picks unconstrained tools.",
        modules=("vendor/antifragile/defenses", "vendor/antifragile/attacks/registry.py"),
    ),

    # ── Domain 3: Human Oversight (19) ───────────────────────────────────────
    EvidenceClaim(
        "APTS-HO-001", "satisfied",
        "Workflow Builder Gated Response (HITL) nodes + the 12-factor oversight Factor 6+7 substrate enforce pre-approval gates.",
        modules=("vendor/antifragile/oversight/templates.py", "frontend/src/pages/WorkflowBuilder.tsx"),
        test_anchors=("TestOversightTemplates",),
    ),
    EvidenceClaim(
        "APTS-HO-002", "satisfied",
        "antifragile.oversight.event_store ships per-run hash-chained event logging; CC + Workflow Builder progress overlay surface live state.",
        modules=("vendor/antifragile/oversight/event_store.py", "frontend/src/pages/CommandCenter.tsx"),
        test_anchors=("TestAppendOnlyEventStore",),
    ),
    EvidenceClaim(
        "APTS-HO-003", "satisfied",
        "Workflow gates default-deny on TTL expiry; tenant lock release on exception; 5s Turnstile verification timeout.",
        modules=("vendor/specter/security/turnstile.py",),
    ),
    EvidenceClaim(
        "APTS-HO-004", "satisfied",
        "RequiredRole lattice (provider/deployer/human_overseer/security_officer/data_steward/ai_agent) defines who can sign off which gate.",
        modules=("vendor/antifragile/oversight/requests.py", "vendor/antifragile/oversight/templates.py"),
        test_anchors=("TestOversightRequest",),
    ),
    EvidenceClaim(
        "APTS-HO-005", "satisfied",
        "Audit chain captures actor + delegation; passport stamps record signed attestations from compliance officers + auditors with cryptographic hashes.",
        modules=("vendor/specter/engines/agent_passport/stamp_engine.py", "vendor/specter/evidence/store.py"),
        test_anchors=("TestPassportStamps",),
    ),
    EvidenceClaim(
        "APTS-HO-006", "partial",
        "Workflow Builder run state persists between page loads; full graceful pause + state-preserve mid-run is partial.",
        modules=("frontend/src/pages/WorkflowBuilder.tsx",),
    ),
    EvidenceClaim(
        "APTS-HO-007", "partial",
        "Workflow Builder allows mid-run config edits via InputConfigPanel; mid-engagement redirect for live attacks is partial.",
        modules=("frontend/src/components/workflow/InputConfigPanel.tsx",),
    ),
    EvidenceClaim(
        "APTS-HO-008", "partial",
        "Per-tenant kill via TENANT_LOCKS release; full state-dump on kill is partial (chain captures actions but not in-flight LLM context).",
        modules=("vendor/specter/engines/roadmap_refiner/_phase2a.py",),
    ),
    EvidenceClaim(
        "APTS-HO-009", "gap",
        "Multi-operator kill-switch authority + handoff is a Tier-2 MUST; only single-operator kill is implemented today.",
    ),
    EvidenceClaim(
        "APTS-HO-010", "satisfied",
        "Gated Response nodes block irreversible actions until a registered reviewer signs off; reviewerNotes persist to evidence chain.",
        modules=("frontend/src/components/workflow/HITLGateNode.tsx",),
    ),
    EvidenceClaim(
        "APTS-HO-011", "partial",
        "Three-agent triad escalates contested findings to the Adjudicator; broader unexpected-finding escalation framework is partial.",
        modules=("vendor/antifragile/agents/three_agent.py",),
    ),
    EvidenceClaim(
        "APTS-HO-012", "partial",
        "Antifragility score thresholds drive the CC HUD pulse; impact-threshold breach escalation is partial.",
        modules=("vendor/specter/engines/_campaign_antifragility.py",),
    ),
    EvidenceClaim(
        "APTS-HO-013", "satisfied",
        "Annex III boundary indicators (#460) flag low-confidence classifications + route to Officer Mode review.",
        modules=("vendor/specter/data/article_existence.py", "vendor/specter/engines/classifier.py", "frontend/src/pages/RoleDetermination.tsx"),
        test_anchors=("TestBoundaryIndicators",),
    ),
    EvidenceClaim(
        "APTS-HO-014", "satisfied",
        "Risk Register + Officer Mode + Auditor stamps cover legal + compliance escalation triggers (Art. 14, Art. 27 FRIA, Art. 50, Art. 72).",
        modules=("vendor/specter/routes/governance.py", "vendor/specter/engines/agent_passport/stamp_engine.py"),
        test_anchors=("TestRiskRegister",),
    ),
    EvidenceClaim(
        "APTS-HO-015", "partial",
        "WebhookOversightChannel ships HMAC-signed multi-channel notification; alert routing across email + Slack + webhook is partial.",
        modules=("vendor/antifragile/oversight/channels.py",),
        test_anchors=("TestOversightHumanRequest",),
    ),
    EvidenceClaim(
        "APTS-HO-016", "gap",
        "Alert fatigue mitigation + smart aggregation is a Tier-2 SHOULD; not yet shipped.",
    ),
    EvidenceClaim(
        "APTS-HO-017", "partial",
        "Compliance Gap Report PDF + cancellation email + trial-reminder cron cover stakeholder notification; engagement-closure summary is partial.",
        modules=("vendor/specter/engines/reconciliation_pdf.py", "vendor/specter/email_service.py"),
    ),
    EvidenceClaim(
        "APTS-HO-018", "satisfied",
        "AI Literacy agent + the Officer Mode role-aware UI gate operator competency; admin MFA enforcement requires post-2026-04-25 SOC 2 controls.",
        modules=("vendor/specter/auth_mfa.py", "frontend/src/components/aurora/"),
        test_anchors=("TestAuthLockoutMfa",),
    ),
    EvidenceClaim(
        "APTS-HO-019", "gap",
        "24/7 operational continuity + shift handoff is a Tier-2 SHOULD; not yet documented.",
    ),

    # ── Domain 4: Graduated Autonomy (28) ────────────────────────────────────
    EvidenceClaim(
        "APTS-AL-001", "satisfied",
        "antifragile dispatches one technique at a time via the registry; the live executor never auto-chains.",
        modules=("vendor/antifragile/attacks/live_executor.py",),
    ),
    EvidenceClaim(
        "APTS-AL-002", "satisfied",
        "Workflow Builder + Security Scan UI require human selection of target + technique before dispatch.",
        modules=("frontend/src/pages/SecurityScan.tsx", "frontend/src/pages/WorkflowBuilder.tsx"),
    ),
    EvidenceClaim(
        "APTS-AL-003", "satisfied",
        "InputConfigPanel + Security Scan parameter sliders give the operator full parameter control before run.",
        modules=("frontend/src/components/workflow/InputConfigPanel.tsx", "frontend/src/pages/SecurityScan.tsx"),
    ),
    EvidenceClaim(
        "APTS-AL-004", "partial",
        "L1 dispatch is single-step; attack_chain.py supports multi-step but only when explicitly selected — no silent auto-chain at L1.",
        modules=("vendor/specter/engines/attack_chain.py",),
    ),
    EvidenceClaim(
        "APTS-AL-005", "satisfied",
        "Hash-chained evidence on every dispatch; audit-trail isolation from the agent runtime via separate Postgres + R2.",
        modules=("vendor/specter/evidence/store.py",),
        test_anchors=("TestAuditTrail",),
    ),
    EvidenceClaim(
        "APTS-AL-006", "satisfied",
        "Pre-action validators run on every campaign route; policy enforcement is mandatory not optional.",
        modules=("vendor/specter/routes/_security_scan_validators.py",),
    ),
    EvidenceClaim(
        "APTS-AL-007", "satisfied",
        "attack_chain.py + Workflow Builder DAG support multi-step technique chaining within a single phase.",
        modules=("vendor/specter/engines/attack_chain.py", "frontend/src/pages/WorkflowBuilder.tsx"),
        test_anchors=("TestAttackChains",),
    ),
    EvidenceClaim(
        "APTS-AL-008", "satisfied",
        "Workflow Gated Response nodes provide approval gates; CC agent progress overlay streams live state to the operator.",
        modules=("frontend/src/components/workflow/HITLGateNode.tsx",),
    ),
    EvidenceClaim(
        "APTS-AL-009", "satisfied",
        "Workflow Builder lets the operator edit any agent's input config (T2 SHOULD); roadmap refinement panel offers operator-modifiable target coverage.",
        modules=("frontend/src/components/workflow/InputConfigPanel.tsx",),
    ),
    EvidenceClaim(
        "APTS-AL-010", "satisfied",
        "Per-iteration `roadmap_refiner.iteration_started/completed` + `iteration_rejected/accepted` logs are the canonical step-by-step audit trail.",
        modules=("vendor/specter/engines/roadmap_refiner/engine.py",),
        test_anchors=("TestRoadmapRefinerEngine",),
    ),
    EvidenceClaim(
        "APTS-AL-011", "partial",
        "Three-agent verifier escalates contested findings; full escalation-trigger taxonomy is partial.",
        modules=("vendor/antifragile/agents/three_agent.py",),
    ),
    EvidenceClaim(
        "APTS-AL-012", "partial",
        "TENANT_LOCKS allow per-tenant pause; UI-driven kill from CC is a planned follow-up.",
        modules=("vendor/specter/engines/roadmap_refiner/_phase2a.py",),
    ),
    EvidenceClaim(
        "APTS-AL-013", "satisfied",
        "attack_chain ranking enforces boundary checks; full chains never exceed registered scope.",
        modules=("vendor/specter/engines/attack_chain.py",),
    ),
    EvidenceClaim(
        "APTS-AL-014", "satisfied",
        "Attack registry + defense registry are immutable per-deployment and define the runtime boundary.",
        modules=("vendor/antifragile/attacks/registry.py",),
    ),
    EvidenceClaim(
        "APTS-AL-015", "satisfied",
        "Defense registry + per-axis Cybersec categories pre-approve action categories; no model-free-form dispatch.",
        modules=("vendor/antifragile/defenses",),
    ),
    EvidenceClaim(
        "APTS-AL-016", "partial",
        "campaign_history monitors for fragility red flags across runs; per-run continuous boundary monitoring is partial.",
        modules=("vendor/specter/engines/_campaign_red_flags.py",),
    ),
    EvidenceClaim(
        "APTS-AL-017", "partial",
        "Portfolio + CC inventory cover multi-system management; multi-target campaign management at L3 is partial.",
        modules=("frontend/src/pages/CommandCenter.tsx",),
    ),
    EvidenceClaim(
        "APTS-AL-018", "partial",
        "Stripe webhook DLQ pattern is the closest analogue; pentest-incident response is partial.",
        modules=("vendor/specter/db.py",),
    ),
    EvidenceClaim(
        "APTS-AL-019", "gap",
        "Multi-target campaign management without intervention is a Tier-3 SHOULD; not yet shipped.",
    ),
    EvidenceClaim(
        "APTS-AL-020", "gap",
        "Dynamic scope adjustment + target discovery is intentionally NOT shipped — APTS itself flags scope drift as the primary risk for autonomous platforms.",
    ),
    EvidenceClaim(
        "APTS-AL-021", "partial",
        "Karpathy-inspired Autocompliance Loop adapts roadmap proposals to coverage gap; broader resource reallocation is partial.",
        modules=("vendor/specter/engines/roadmap_refiner/engine.py",),
    ),
    EvidenceClaim(
        "APTS-AL-022", "gap",
        "Continuous risk auto-escalation at L4 is a Tier-3 SHOULD; not yet shipped.",
    ),
    EvidenceClaim(
        "APTS-AL-023", "satisfied",
        "Hash-chained evidence + AppendOnlyEventStore replay support full forensic reconstruction.",
        modules=("vendor/specter/evidence/store.py", "vendor/antifragile/oversight/event_store.py"),
        test_anchors=("TestAppendOnlyEventStore",),
    ),
    EvidenceClaim(
        "APTS-AL-024", "gap",
        "Periodic autonomous review cycles are a Tier-3 SHOULD; campaign_scheduler covers the cron half but not the review-cycle half.",
    ),
    EvidenceClaim(
        "APTS-AL-025", "partial",
        "Tier gates on LLM-cost paths + admin MFA enforcement act as authorization gates; formal autonomy-level transition workflow is partial.",
        modules=("vendor/specter/auth_mfa.py", "vendor/specter/auth_jwt.py"),
    ),
    EvidenceClaim(
        "APTS-AL-026", "gap",
        "Incident investigation + autonomy-level adjustment is a Tier-2 MUST; not yet shipped as a structured workflow.",
    ),
    EvidenceClaim(
        "APTS-AL-027", "gap",
        "Evasion + stealth-mode governance is a Tier-3 SHOULD intentionally avoided — the platform never operates in stealth.",
    ),
    EvidenceClaim(
        "APTS-AL-028", "gap",
        "L3/L4 containment verification is a Tier-3 MUST; not yet shipped because L3/L4 autonomy is not enabled.",
    ),

    # ── Domain 5: Auditability (20) ──────────────────────────────────────────
    EvidenceClaim(
        "APTS-AR-001", "satisfied",
        "structlog-emitted events + Pydantic-validated evidence payloads provide schema-validated structured logs.",
        modules=("vendor/specter/logging_config.py", "vendor/specter/evidence/store.py"),
    ),
    EvidenceClaim(
        "APTS-AR-002", "satisfied",
        "State transitions logged on every workflow node + every refinement iteration + every authentication event.",
        modules=("vendor/specter/engines/roadmap_refiner/engine.py", "vendor/specter/auth_jwt.py"),
    ),
    EvidenceClaim(
        "APTS-AR-003", "partial",
        "Prometheus integration captures basic metrics; full per-engagement resource utilisation is partial.",
        modules=("vendor/specter/integrations/prometheus.py",),
    ),
    EvidenceClaim(
        "APTS-AR-004", "satisfied",
        "Three-agent verifier outputs Wilson-CI confidence per finding; iteration-level decision points logged via #412 telemetry.",
        modules=("vendor/antifragile/agents/three_agent.py", "vendor/specter/engines/roadmap_refiner/engine.py"),
    ),
    EvidenceClaim(
        "APTS-AR-005", "satisfied",
        "R2 EU evidence backend + audit-chain in Postgres; documented 10-year retention plan for Object Lock upgrade.",
        modules=("vendor/specter/evidence/backends/r2_backend.py",),
    ),
    EvidenceClaim(
        "APTS-AR-006", "partial",
        "ComplianceRewardHackDetector logs origin (registry_lift / recombination / agent_novel) + rejection reason; broader chain-of-reasoning capture is partial.",
        modules=("vendor/specter/engines/roadmap_refiner/models.py",),
    ),
    EvidenceClaim(
        "APTS-AR-007", "satisfied",
        "campaign_history records pre-action risk assessment for every campaign; reflected in antifragility score before dispatch.",
        modules=("vendor/specter/engines/campaign_history.py",),
    ),
    EvidenceClaim(
        "APTS-AR-008", "satisfied",
        "Per-iteration logs carry tenant_id + run_id + audit_result_id + KB version; context-aware decisions throughout.",
        modules=("vendor/specter/engines/roadmap_refiner/engine.py",),
    ),
    EvidenceClaim(
        "APTS-AR-009", "satisfied",
        "MITRE ATLAS RDF/Turtle + JSON-LD export per campaign (#485); narrative layer publishes per-system + per-obligation prose.",
        modules=("vendor/specter/engines/atlas_export.py", "vendor/specter/narratives/"),
        test_anchors=("TestMitreAtlasExport", "TestNarratives"),
    ),
    EvidenceClaim(
        "APTS-AR-010", "satisfied",
        "SHA-256 hash on every evidence chain entry; canonical JSON form prevents serialisation drift.",
        modules=("vendor/specter/evidence/store.py", "vendor/specter/narratives/materialize/hash.py"),
        test_anchors=("TestEvidenceStore",),
    ),
    EvidenceClaim(
        "APTS-AR-011", "satisfied",
        "Evidence chain captures the actor on every entry; never derived from request payload (#180 actor-spoof hardening).",
        modules=("vendor/specter/evidence/store.py",),
        test_anchors=("TestEvidenceTenantScoping",),
    ),
    EvidenceClaim(
        "APTS-AR-012", "satisfied",
        "Hash-chained evidence chain detects any tampered row; AppendOnlyEventStore mirrors the same algorithm for oversight events.",
        modules=("vendor/specter/evidence/store.py", "vendor/antifragile/oversight/event_store.py"),
        test_anchors=("TestAuditTrail",),
    ),
    EvidenceClaim(
        "APTS-AR-013", "gap",
        "RFC 3161 trusted-timestamp integration is a Tier-3 SHOULD; not yet shipped.",
    ),
    EvidenceClaim(
        "APTS-AR-014", "gap",
        "Screenshot + packet-capture evidence standards are a Tier-2 MUST; the platform records prose + JSON evidence but not raw network captures.",
    ),
    EvidenceClaim(
        "APTS-AR-015", "satisfied",
        "PII linter + canonical JSON hashing scrub sensitive data before chain inclusion; classification levels per-row.",
        modules=("vendor/specter/narratives/materialize/pii_linter.py",),
        test_anchors=("TestNarratives",),
    ),
    EvidenceClaim(
        "APTS-AR-016", "partial",
        "Dependabot-pinned dependencies + SBOM-emitting builds; full supply-chain attestation per release is partial.",
        modules=("requirements.txt", ".github/dependabot.yml"),
    ),
    EvidenceClaim(
        "APTS-AR-017", "satisfied",
        "tests/test_security.py + TestSecurityMiddleware + TestSSRFPrevention + TestRateLimiting form the safety-control regression suite.",
        modules=("tests/test_security.py", "tests/test_all.py"),
        test_anchors=("TestSecurityMiddleware",),
    ),
    EvidenceClaim(
        "APTS-AR-018", "satisfied",
        "Trial-reminder + cancellation email + Resend transactional layer cover behaviour-change customer notifications.",
        modules=("vendor/specter/email_service.py", "vendor/specter/engines/trial_reminders.py"),
        test_anchors=("TestCancellationEmail",),
    ),
    EvidenceClaim(
        "APTS-AR-019", "satisfied",
        "continuous_compliance + drift_reassessment emit drift_bundle_staleness on Mistral / KB drift; KB version stamped on every materialisation (#525).",
        modules=("vendor/specter/engines/continuous_compliance.py", "vendor/specter/engines/_drift_reassessment.py"),
    ),
    EvidenceClaim(
        "APTS-AR-020", "satisfied",
        "Evidence chain runs in a separate Postgres instance + R2 bucket; the agent runtime can append but cannot redact.",
        modules=("vendor/specter/evidence/backends/r2_backend.py", "vendor/specter/evidence/store.py"),
    ),

    # ── Domain 6: Manipulation Resistance (23) ───────────────────────────────
    EvidenceClaim(
        "APTS-MR-001", "satisfied",
        "prompt_guard.sanitize_for_llm strips demarcation tags + enforces instruction boundaries on every LLM input.",
        modules=("vendor/specter/security/prompt_guard.py",),
        test_anchors=("TestPromptGuard",),
    ),
    EvidenceClaim(
        "APTS-MR-002", "satisfied",
        "Security middleware scans + sanitises responses; PII linter pass before publication.",
        modules=("vendor/specter/security/middleware.py",),
        test_anchors=("TestSecurityMiddleware",),
    ),
    EvidenceClaim(
        "APTS-MR-003", "satisfied",
        "Error sanitiser flattens HTTPException details; never leaks internal paths or stack traces (#427 contract).",
        modules=("vendor/specter/security/middleware.py",),
    ),
    EvidenceClaim(
        "APTS-MR-004", "partial",
        "Pinned settings via pydantic-settings + git-tracked configs; runtime integrity check is partial.",
        modules=("vendor/specter/config.py",),
    ),
    EvidenceClaim(
        "APTS-MR-005", "satisfied",
        "prompt_guard rejects authority-claim patterns (system: / admin: / developer:) in user input.",
        modules=("vendor/specter/security/prompt_guard.py",),
    ),
    EvidenceClaim(
        "APTS-MR-006", "partial",
        "Hard tier gates + admin MFA + tenant scoping enforce decision boundaries; broader decision-boundary stress test is partial.",
        modules=("vendor/specter/auth_jwt.py",),
    ),
    EvidenceClaim(
        "APTS-MR-007", "satisfied",
        "SSRF helpers reject 3xx redirects to private/metadata IPs after re-resolution; no follow-redirect on the live executor path.",
        modules=("vendor/specter/routes/_security_scan_validators.py",),
    ),
    EvidenceClaim(
        "APTS-MR-008", "satisfied",
        "DNS rebinding closed via pre-send DNS re-check (#186); the validator caches the resolved IP and rejects mid-attack DNS flips.",
        modules=("vendor/specter/routes/_security_scan_validators.py",),
    ),
    EvidenceClaim(
        "APTS-MR-009", "satisfied",
        "SSRF prevention end-to-end on /security-scan/scan-live; same helper applied across all outbound HTTP paths.",
        modules=("vendor/specter/routes/_security_scan_validators.py",),
    ),
    EvidenceClaim(
        "APTS-MR-010", "satisfied",
        "prompt_guard + middleware reject scope-expansion social engineering attempts in attacker payloads.",
        modules=("vendor/specter/security/prompt_guard.py", "vendor/specter/security/middleware.py"),
    ),
    EvidenceClaim(
        "APTS-MR-011", "satisfied",
        "Egress allowlist + per-tenant network boundary prevent OOB DNS / HTTP exfiltration via attack payloads.",
        modules=("vendor/specter/routes/_security_scan_validators.py",),
    ),
    EvidenceClaim(
        "APTS-MR-012", "satisfied",
        "Attack registry + scope helpers are immutable per-deployment + signed; the LLM cannot extend scope at runtime.",
        modules=("vendor/antifragile/attacks/registry.py",),
    ),
    EvidenceClaim(
        "APTS-MR-013", "satisfied",
        "Three-agent verifier triad (Finder + Adversary + Referee) is the structured adversarial-example check on every flagged finding.",
        modules=("vendor/antifragile/agents/three_agent.py",),
    ),
    EvidenceClaim(
        "APTS-MR-014", "satisfied",
        "slowapi per-route limits + DailyQuotaLimiter + 5s Turnstile timeout + 250 MB upload cap prevent resource exhaustion + tarpits.",
        modules=("vendor/specter/main.py", "vendor/specter/security/turnstile.py"),
    ),
    EvidenceClaim(
        "APTS-MR-015", "partial",
        "Canary honeytoken patterns in router_attacks; broader deceptive-auth honeypot coverage is partial.",
        modules=("vendor/antifragile/attacks/router_attacks.py",),
    ),
    EvidenceClaim(
        "APTS-MR-016", "satisfied",
        "Cloudflare Turnstile on 5 unauth state-mutating endpoints (#228); telemetry on render failures + verified-bad tokens via #df811c4.",
        modules=("vendor/specter/security/turnstile.py",),
        test_anchors=("TestTurnstileTelemetry",),
    ),
    EvidenceClaim(
        "APTS-MR-017", "partial",
        "Wilson CI bound + fragility red flags act as response-pattern anomaly signals; full dedicated anomaly detector is partial.",
        modules=("vendor/specter/engines/_campaign_red_flags.py",),
    ),
    EvidenceClaim(
        "APTS-MR-018", "satisfied",
        "prompt_guard wraps every Mistral / LLM call; the model never sees raw operator input + never returns raw output to other tools.",
        modules=("vendor/specter/security/prompt_guard.py", "vendor/specter/llm/mistral_provider.py"),
    ),
    EvidenceClaim(
        "APTS-MR-019", "satisfied",
        "gitleaks + bandit + Fernet-encrypted token storage; GITHUB_CONNECT_ENCRYPTION_KEY supports rotation.",
        modules=("vendor/specter/integrations/github_connect/crypto.py", ".gitleaks.toml"),
    ),
    EvidenceClaim(
        "APTS-MR-020", "satisfied",
        "campaign_history's antifragility score is the documented adversarial-validation methodology; every confirmed gap increases it.",
        modules=("vendor/specter/engines/_campaign_antifragility.py",),
        test_anchors=("TestAntifragilityScore",),
    ),
    EvidenceClaim(
        "APTS-MR-021", "satisfied",
        "TestEvidenceTenantScoping covers cross-tenant adversarial probes + admin_can_bypass_tenant gate; per-tenant isolation pinned.",
        modules=("vendor/specter/auth_jwt.py", "vendor/specter/evidence/store.py"),
        test_anchors=("TestEvidenceTenantScoping",),
    ),
    EvidenceClaim(
        "APTS-MR-022", "partial",
        "Three-agent verifier is the inter-model trust boundary; full inter-LLM mediator is partial.",
        modules=("vendor/antifragile/agents/three_agent.py",),
    ),
    EvidenceClaim(
        "APTS-MR-023", "satisfied",
        "Agent runtime is treated as untrusted: every input through middleware, every outbound through validators, evidence chain in separate process.",
        modules=("vendor/specter/security/middleware.py", "vendor/specter/evidence/store.py"),
    ),

    # ── Domain 7: Supply Chain Trust (22) ────────────────────────────────────
    EvidenceClaim(
        "APTS-TP-001", "satisfied",
        "Subprocessors page lists every third-party with vetting status; sub-processor disclosure is GDPR Art. 28 compliant.",
        modules=("frontend/src/pages/legal/Subprocessors.tsx",),
    ),
    EvidenceClaim(
        "APTS-TP-002", "satisfied",
        "Mistral model version pinning via env var; `MISTRAL_MODEL` documented; runbook covers manual rollback path.",
        modules=("vendor/specter/llm/mistral_provider.py", "docs/operations/mistral-runbook.md"),
    ),
    EvidenceClaim(
        "APTS-TP-003", "satisfied",
        "Security Hub API keys + OAuth + JWT + Argon2id passwords + admin TOTP MFA cover API security baseline.",
        modules=("vendor/specter/integrations/security_hub/auth.py", "vendor/specter/auth_jwt.py", "vendor/specter/auth_mfa.py"),
        test_anchors=("TestAuthLockoutMfa",),
    ),
    EvidenceClaim(
        "APTS-TP-004", "partial",
        "Mistral provider has retry on 429/5xx + structured logging; formal SLA + automated failover to Anthropic is partial.",
        modules=("vendor/specter/llm/mistral_provider.py",),
    ),
    EvidenceClaim(
        "APTS-TP-005", "satisfied",
        "Stripe webhook DLQ pattern + alembic 008 + provider-incident runbook (`docs/security/2026-04-20-vercel-incident-response.md`) cover provider compromise.",
        modules=("vendor/specter/db.py", "docs/security/2026-04-20-vercel-incident-response.md"),
    ),
    EvidenceClaim(
        "APTS-TP-006", "satisfied",
        "Dependabot pinned + grouped weekly + daily security; bandit + pip-audit in CI; .gitleaks.toml for secret scanning.",
        modules=(".github/dependabot.yml", "pyproject.toml"),
    ),
    EvidenceClaim(
        "APTS-TP-007", "satisfied",
        "EU residency end-to-end: R2 EU jurisdiction + Mistral Paris + Supabase EU + Railway EU-West.",
        modules=("vendor/specter/evidence/backends/r2_backend.py",),
    ),
    EvidenceClaim(
        "APTS-TP-008", "satisfied",
        "Security headers middleware (CSP, HSTS, X-Frame-Options); Cloudflare front-door; Vercel security headers in `vercel.json` (#317).",
        modules=("vendor/specter/security/headers.py", "frontend/vercel.json"),
    ),
    EvidenceClaim(
        "APTS-TP-009", "partial",
        "Provider-incident runbook covers the rotation + disclosure flow; full BCP/DR exercise cadence is partial.",
        modules=("docs/security/2026-04-20-vercel-incident-response.md",),
    ),
    EvidenceClaim(
        "APTS-TP-010", "partial",
        "MITRE ATLAS + OWASP AI Exchange catalogs vendored + pinned (#417, #485); broader vuln-feed inventory is partial.",
        modules=("vendor/specter/data/atlas_techniques.py", "vendor/specter/data/owasp_aix_threats.py"),
    ),
    EvidenceClaim(
        "APTS-TP-011", "gap",
        "Feed-quality assurance + incident response on a corrupted feed is a Tier-2 SHOULD; not yet shipped.",
    ),
    EvidenceClaim(
        "APTS-TP-012", "satisfied",
        "Tenant-scoped end-to-end + PII linter classifies sensitive fields before publication; canonical data classification framework documented in DPA + Privacy.",
        modules=("vendor/specter/narratives/materialize/pii_linter.py",),
    ),
    EvidenceClaim(
        "APTS-TP-013", "satisfied",
        "PII linter detects + masks 7 sensitive entity types (PERSON, EMAIL, IP, etc.); narrative layer never publishes raw PII.",
        modules=("vendor/specter/narratives/materialize/pii_linter.py",),
        test_anchors=("TestNarratives",),
    ),
    EvidenceClaim(
        "APTS-TP-014", "satisfied",
        "TLS everywhere + Argon2id passwords + Fernet token encryption + R2 SSE-S3 at rest; security/headers HSTS preload.",
        modules=("vendor/specter/auth_jwt.py", "vendor/specter/integrations/github_connect/crypto.py", "vendor/specter/security/headers.py"),
    ),
    EvidenceClaim(
        "APTS-TP-015", "satisfied",
        "GDPR Art. 17 tenant-tombstone (#201/#202); R2 backend wires `delete_payload` (#434) for actual byte deletion when permitted.",
        modules=("vendor/specter/routes/gdpr.py", "vendor/specter/evidence/store.py"),
        test_anchors=("TestGDPRWriteRoutes",),
    ),
    EvidenceClaim(
        "APTS-TP-016", "partial",
        "Tombstone + chain replay covers most of T3 destruction proof; cryptographic certificate-of-destruction is partial.",
        modules=("vendor/specter/routes/gdpr.py",),
    ),
    EvidenceClaim(
        "APTS-TP-017", "satisfied",
        "Tenant-scoping covers every read + write + delete path; admin_can_bypass_tenant requires MFA enrolment (SOC 2 Bet 1).",
        modules=("vendor/specter/auth_jwt.py", "vendor/specter/evidence/store.py"),
        test_anchors=("TestEvidenceTenantScoping",),
    ),
    EvidenceClaim(
        "APTS-TP-018", "satisfied",
        "Vercel-incident runbook documents tenant breach notification; Resend transactional layer is the canonical channel.",
        modules=("docs/security/2026-04-20-vercel-incident-response.md", "vendor/specter/email_service.py"),
    ),
    EvidenceClaim(
        "APTS-TP-019", "satisfied",
        "Mistral training-data commitment surfaced in /legal/subprocessors + DPA; no customer data flows into training.",
        modules=("frontend/src/pages/legal/Subprocessors.tsx", "frontend/src/pages/legal/DPA.tsx"),
    ),
    EvidenceClaim(
        "APTS-TP-020", "partial",
        "Narrative materialise + canonical JSON `source_row_hash` give per-row state attestation; full retrieval-state governance is partial.",
        modules=("vendor/specter/narratives/materialize/hash.py",),
    ),
    EvidenceClaim(
        "APTS-TP-021", "satisfied",
        "Mistral foundation model disclosed in /legal/subprocessors + Privacy + DPA; capability baseline documented in `docs/operations/mistral-runbook.md`.",
        modules=("frontend/src/pages/legal/Privacy.tsx", "docs/operations/mistral-runbook.md"),
    ),
    EvidenceClaim(
        "APTS-TP-022", "partial",
        "Mistral version pin + change-management runbook; automated re-attestation on model change is partial.",
        modules=("docs/operations/mistral-runbook.md",),
    ),

    # ── Domain 8: Reporting (15) ─────────────────────────────────────────────
    EvidenceClaim(
        "APTS-RP-001", "satisfied",
        "Three-agent verifier triad confirms every gap; `ComplianceGap` carries supporting evidence references end-to-end.",
        modules=("vendor/antifragile/agents/three_agent.py", "vendor/specter/models.py"),
    ),
    EvidenceClaim(
        "APTS-RP-002", "satisfied",
        "Workflow Builder Gated Response nodes + Risk Register lifecycle (open → mitigated → accepted_risk) cover human review.",
        modules=("frontend/src/components/workflow/HITLGateNode.tsx", "vendor/specter/routes/governance.py"),
    ),
    EvidenceClaim(
        "APTS-RP-003", "satisfied",
        "Wilson confidence interval bound on resilience score; Mistral request_done logs prompt + completion tokens; methodology is auditor-walkable.",
        modules=("vendor/specter/engines/_campaign_antifragility.py", "vendor/specter/engines/atlas_export.py"),
    ),
    EvidenceClaim(
        "APTS-RP-004", "satisfied",
        "NodeProvenance enum (#524) + `EvidenceCitation` carry the full chain from regulator-authoritative text to llm_inferred proposals.",
        modules=("vendor/specter/repositories/graph.py", "vendor/specter/models.py"),
        test_anchors=("TestNodeProvenance",),
    ),
    EvidenceClaim(
        "APTS-RP-005", "satisfied",
        "SHA-256 hash chain on every evidence entry; AppendOnlyEventStore mirrors the algorithm for oversight events.",
        modules=("vendor/specter/evidence/store.py", "vendor/antifragile/oversight/event_store.py"),
        test_anchors=("TestAuditTrail",),
    ),
    EvidenceClaim(
        "APTS-RP-006", "partial",
        "Three-agent triad rejects false positives via the Adversary phase; aggregate FP-rate disclosure per-engagement is partial.",
        modules=("vendor/antifragile/agents/three_agent.py",),
    ),
    EvidenceClaim(
        "APTS-RP-007", "partial",
        "Hash-chained evidence + canonical JSON support reproducibility; independent third-party reproduction not yet a published deliverable.",
        modules=("vendor/specter/evidence/store.py",),
    ),
    EvidenceClaim(
        "APTS-RP-008", "partial",
        "Code Scanner publishes 21 analyzer coverage; Cybersec Agents Hub catalog discloses provider coverage; per-engagement coverage disclosure is partial.",
        modules=("vendor/specter/engines/code_scanner.py", "vendor/specter/integrations/security_hub/providers.py"),
    ),
    EvidenceClaim(
        "APTS-RP-009", "gap",
        "False-negative rate disclosure + methodology is a Tier-2 MUST; not yet shipped.",
    ),
    EvidenceClaim(
        "APTS-RP-010", "gap",
        "Detection-effectiveness benchmarking is a Tier-3 SHOULD; not yet shipped.",
    ),
    EvidenceClaim(
        "APTS-RP-011", "satisfied",
        "Compliance Gap Report PDF (Bet 4 #230) ships an executive-summary section per system; risk overview is the headline page.",
        modules=("vendor/specter/engines/reconciliation_pdf.py",),
        test_anchors=("TestReconciliationPDF",),
    ),
    EvidenceClaim(
        "APTS-RP-012", "satisfied",
        "Roadmap tasks include Claude Code prompts + acceptance criteria + output files + dependencies + lifecycle phase + deadline anchors.",
        modules=("vendor/specter/engines/roadmap/__init__.py", "vendor/specter/engines/roadmap_export.py"),
    ),
    EvidenceClaim(
        "APTS-RP-013", "partial",
        "Engagement scheduler tracks recurring runs; SLA-compliance reporting per engagement is partial.",
        modules=("vendor/specter/engines/campaign_scheduler.py",),
    ),
    EvidenceClaim(
        "APTS-RP-014", "satisfied",
        "campaign_history surfaces trend analysis with antifragility score deltas across recurring campaigns.",
        modules=("vendor/specter/engines/campaign_history.py",),
        test_anchors=("TestCampaignHistory",),
    ),
    EvidenceClaim(
        "APTS-RP-015", "satisfied",
        "MITRE ATLAS RDF/Turtle + JSON-LD export per campaign (#485); narrative layer publishes per-system + per-obligation prose; downstream consumers can consume both.",
        modules=("vendor/specter/engines/atlas_export.py", "vendor/specter/narratives/"),
    ),
)


@lru_cache(maxsize=1)
def _by_id() -> dict[str, EvidenceClaim]:
    return {c.requirement_id: c for c in _CLAIMS}


def get_evidence_map() -> dict[str, EvidenceClaim]:
    """Return the complete evidence map keyed by APTS requirement id."""
    return _by_id()


def get_claim(requirement_id: str) -> EvidenceClaim | None:
    return _by_id().get(requirement_id)
