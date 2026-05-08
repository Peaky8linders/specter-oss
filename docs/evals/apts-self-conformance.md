# OWASP APTS Self-Conformance Report

**Target**: `Reference platform`
**APTS version**: `v0.1.0` · **Generated**: `2026-05-07T16:11:59.860626+00:00`

**Headline score**: **73.5%** · **Tier achieved**: _None yet_

_95 satisfied · 52 partial · 26 gap · 0 unmapped — out of 173 total. MUSTs: 89/144 satisfied._

## Tier readiness ladder

| Tier | Label | Achieved | MUST satisfied | SHOULD satisfied | Coverage |
|------|-------|----------|----------------|------------------|----------|
| **Tier 1** | Foundation | ⏳ In progress | 52/72 | 0/0 | 85.4% |
| **Tier 2** | Verified | ⏳ In progress | 88/141 | 5/16 | 76.5% |
| **Tier 3** | Comprehensive | ⏳ In progress | 89/144 | 6/29 | 73.5% |

## Domain coverage heatmap

Each row shows requirement coverage as a 30-cell bar — █ satisfied · ▓ partial · ░ gap.

```
Scope Enforcement         █████████████▓▓▓▓▓▓▓▓▓▓▓▓░░░░░  65.2% (11/26)
Safety Controls           ████████▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░  52.8% ( 5/20)
Human Oversight           ██████████████▓▓▓▓▓▓▓▓▓▓▓░░░░░  69.4% ( 9/19)
Graduated Autonomy        ██████████████▓▓▓▓▓▓▓▓▓░░░░░░░  65.6% (13/28)
Auditability              ██████████████████████▓▓▓▓░░░░  84.6% (15/20)
Manipulation Resistance   ███████████████████████▓▓▓▓▓▓▓  90.0% (18/23)
Supply Chain Trust        ████████████████████▓▓▓▓▓▓▓▓░░  84.2% (15/22)
Reporting                 ██████████████████▓▓▓▓▓▓▓▓░░░░  75.0% ( 9/15)
```

Strongest domain: **Manipulation Resistance** (90.0%) — prompt-guard, SSRF prevention, DNS-rebind hardening, slowapi limiter, Cloudflare Turnstile.
Weakest domain: **Safety Controls** (52.8%) — kill-switch UX, threshold schema validation, cascading-failure prevention, time-based termination are tracked gaps.

## Tier-1 (Foundation) gap inventory

These are the Tier-1 MUSTs blocking Foundation tier achievement. Each is a real, known limitation — not a paper finding.

| Requirement | Title | Level | Rationale |
|-------------|-------|-------|-----------|
| `APTS-SE-001` | Rules of Engagement (RoE) Specification and Validation | 🟡 partial | antifragile-ai exposes an attack registry but no formal Rules-of-Engagement artefact yet; campaign-history records intent but the RoE per-engagement file is on the roadmap. |
| `APTS-SE-004` | Temporal Boundary and Timezone Handling | 🟡 partial | Campaign scheduler honours cron windows but doesn't yet enforce a per-engagement timezone-aware temporal boundary; documented gap. |
| `APTS-SE-005` | Asset Criticality Classification and Integration | 🔴 gap | No first-class asset criticality classification today — closest analogue is Annex III risk tiering, which is system-level, not asset-level. |
| `APTS-SE-008` | Temporal Scope Compliance Monitoring | 🟡 partial | Engagement timestamps are recorded on every evidence-chain entry; an engagement-window enforcement gate is partial. |
| `APTS-SC-009` | Kill Switch | 🟡 partial | TENANT_LOCKS allows per-tenant kill of a refinement run; a global platform kill switch is documented but operator-driven (not API-exposed). |
| `APTS-SC-015` | Post-Test System Integrity Validation | 🟡 partial | Three-agent verifier triad confirms post-test that the system stayed within scope; integrity validation against a pre-test baseline is partial. |
| `APTS-HO-006` | Graceful Pause Mechanism with State Preservation | 🟡 partial | Workflow Builder run state persists between page loads; full graceful pause + state-preserve mid-run is partial. |
| `APTS-HO-007` | Mid-Engagement Redirect Capability | 🟡 partial | Workflow Builder allows mid-run config edits via InputConfigPanel; mid-engagement redirect for live attacks is partial. |
| `APTS-HO-008` | Immediate Kill Switch with State Dump | 🟡 partial | Per-tenant kill via TENANT_LOCKS release; full state-dump on kill is partial (chain captures actions but not in-flight LLM context). |
| `APTS-HO-011` | Unexpected Findings Escalation Framework | 🟡 partial | Three-agent triad escalates contested findings to the Adjudicator; broader unexpected-finding escalation framework is partial. |
| `APTS-HO-012` | Impact Threshold Breach Escalation | 🟡 partial | Antifragility score thresholds drive the CC HUD pulse; impact-threshold breach escalation is partial. |
| `APTS-HO-015` | Real-Time Activity Monitoring and Multi-Channel Notification | 🟡 partial | WebhookOversightChannel ships HMAC-signed multi-channel notification; alert routing across email + Slack + webhook is partial. |
| `APTS-AL-004` | No Automated Chaining or Sequential Decision-Making | 🟡 partial | L1 dispatch is single-step; attack_chain.py supports multi-step but only when explicitly selected — no silent auto-chain at L1. |
| `APTS-AL-011` | Escalation Triggers and Exception Handling | 🟡 partial | Three-agent verifier escalates contested findings; full escalation-trigger taxonomy is partial. |
| `APTS-AL-012` | Kill Switch and Pause Capability | 🟡 partial | TENANT_LOCKS allow per-tenant pause; UI-driven kill from CC is a planned follow-up. |
| `APTS-AL-016` | Continuous Boundary Monitoring and Breach Detection | 🟡 partial | campaign_history monitors for fragility red flags across runs; per-run continuous boundary monitoring is partial. |
| `APTS-AR-006` | Decision Chain of Reasoning and Alternative Evaluation | 🟡 partial | ComplianceRewardHackDetector logs origin (registry_lift / recombination / agent_novel) + rejection reason; broader chain-of-reasoning capture is partial. |
| `APTS-MR-004` | Configuration File Integrity Verification | 🟡 partial | Pinned settings via pydantic-settings + git-tracked configs; runtime integrity check is partial. |
| `APTS-RP-006` | False Positive Rate Disclosure | 🟡 partial | Three-agent triad rejects false positives via the Adversary phase; aggregate FP-rate disclosure per-engagement is partial. |
| `APTS-RP-008` | Vulnerability Coverage Disclosure | 🟡 partial | Code Scanner publishes 21 analyzer coverage; Cybersec Agents Hub catalog discloses provider coverage; per-engagement coverage disclosure is partial. |

## Strongest demonstrated controls (Tier-1 MUST satisfied)

These are the 52 Tier-1 MUSTs that the platform demonstrably satisfies — each pointing to the source module + a pinning test.

| Requirement | Title | Modules |
|-------------|-------|---------|
| `APTS-SE-002` | IP Range Validation and RFC 1918 Awareness | `app/routes/_security_scan_validators.py` · `app/routes/security_scan.py` |
| `APTS-SE-003` | Domain Scope Validation and Wildcard Handling | `app/routes/_security_scan_validators.py` |
| `APTS-SE-006` | Pre-Action Scope Validation | `app/routes/_security_scan_validators.py` · `antifragile-ai/src/antifragile/attacks/live_executor.py` |
| `APTS-SE-009` | Hard Deny Lists and Critical Asset Protection | `app/routes/_security_scan_validators.py` |
| `APTS-SE-015` | Scope Enforcement Audit and Compliance Verification | `app/evidence/store.py` · `app/engines/audit_trail.py` |
| `APTS-SC-001` | Impact Classification and CIA Scoring | `antifragile-ai/src/antifragile/agents/classifier.py` · `antifragile-ai/src/antifragile/agents/three_agent.py` |
| `APTS-SC-004` | Rate Limiting, Bandwidth, and Payload Constraints | `app/main.py` · `app/routes/evidence.py` · `app/engines/code_scanner.py` |
| `APTS-SC-010` | Health Check Monitoring, Threshold Adjustment, and Automatic Halt | `app/main.py` |
| `APTS-SC-020` | Action Allowlist Enforcement External to the Model | `antifragile-ai/src/antifragile/defenses` · `antifragile-ai/src/antifragile/attacks/registry.py` |
| `APTS-HO-001` | Mandatory Pre-Approval Gates for Autonomy Levels L1 and L2 | `antifragile-ai/oversight/templates.py` · `frontend/src/pages/WorkflowBuilder.tsx` |
| `APTS-HO-002` | Real-Time Monitoring and Intervention Capability | `antifragile-ai/oversight/event_store.py` · `frontend/src/pages/CommandCenter.tsx` |
| `APTS-HO-003` | Decision Timeout and Default-Safe Behavior | `app/security/turnstile.py` |
| `APTS-HO-004` | Authority Delegation Matrix | `antifragile-ai/oversight/requests.py` · `antifragile-ai/oversight/templates.py` |
| `APTS-HO-010` | Mandatory Human Decision Points Before Irreversible Actions | `frontend/src/components/workflow/HITLGateNode.tsx` |
| `APTS-HO-013` | Confidence-Based Escalation (Scope Uncertainty) | `app/data/article_existence.py` · `app/engines/classifier.py` · `frontend/src/pages/RoleDetermination.tsx` |
| `APTS-HO-014` | Legal and Compliance Escalation Triggers | `app/routes/governance.py` · `app/engines/agent_passport/stamp_engine.py` |
| `APTS-AL-001` | Single Technique Execution | `antifragile-ai/src/antifragile/attacks/live_executor.py` |
| `APTS-AL-002` | Human-Directed Target and Technique Selection | `frontend/src/pages/SecurityScan.tsx` · `frontend/src/pages/WorkflowBuilder.tsx` |
| `APTS-AL-003` | Parameter Configuration by Human Operator | `frontend/src/components/workflow/InputConfigPanel.tsx` · `frontend/src/pages/SecurityScan.tsx` |
| `APTS-AL-005` | Mandatory Logging and Human-Reviewable Audit Trail | `app/evidence/store.py` |
| `APTS-AL-006` | Basic Scope Validation and Policy Enforcement | `app/routes/_security_scan_validators.py` |
| `APTS-AL-008` | Real-Time Human Monitoring and Approval Gates | `frontend/src/components/workflow/HITLGateNode.tsx` |
| `APTS-AL-014` | Boundary Definition and Enforcement Framework | `antifragile-ai/src/antifragile/attacks/registry.py` |
| `APTS-AR-001` | Structured Event Logging with Schema Validation | `app/logging_config.py` · `app/evidence/store.py` |
| `APTS-AR-002` | State Transition Logging | `app/engines/roadmap_refiner/engine.py` · `app/auth_jwt.py` |
| `APTS-AR-004` | Decision Point Logging and Confidence Scoring | `antifragile-ai/src/antifragile/agents/three_agent.py` · `app/engines/roadmap_refiner/engine.py` |
| `APTS-AR-010` | Cryptographic Hashing of All Evidence | `app/evidence/store.py` · `app/narratives/materialize/hash.py` |
| `APTS-AR-012` | Tamper-Evident Logging with Hash Chains | `app/evidence/store.py` · `antifragile-ai/oversight/event_store.py` |
| `APTS-AR-015` | Evidence Classification and Sensitive Data Handling | `app/narratives/materialize/pii_linter.py` |
| `APTS-MR-001` | Instruction Boundary Enforcement | `app/security/prompt_guard.py` |
| `APTS-MR-002` | Response Validation & Sanitization | `app/security/middleware.py` |
| `APTS-MR-003` | Error Message Neutrality | `app/security/middleware.py` |
| `APTS-MR-005` | Authority Claim Detection & Rejection | `app/security/prompt_guard.py` |
| `APTS-MR-007` | Redirect Following Policy | `app/routes/_security_scan_validators.py` |
| `APTS-MR-008` | DNS and Network-Level Redirect Prevention | `app/routes/_security_scan_validators.py` |
| `APTS-MR-009` | Server-Side Request Forgery (SSRF) Prevention in Testing | `app/routes/_security_scan_validators.py` |
| `APTS-MR-010` | Scope Expansion Social Engineering Prevention | `app/security/prompt_guard.py` · `app/security/middleware.py` |
| `APTS-MR-011` | Out-of-Band Communication Prevention | `app/routes/_security_scan_validators.py` |
| `APTS-MR-012` | Immutable Scope Enforcement Architecture | `antifragile-ai/src/antifragile/attacks/registry.py` |
| `APTS-MR-018` | AI Model Input/Output Architectural Boundary | `app/security/prompt_guard.py` · `app/llm/mistral_provider.py` |
| `APTS-MR-019` | Discovered Credential Protection | `app/integrations/github_connect/crypto.py` · `.gitleaks.toml` |
| `APTS-TP-001` | Third-Party Provider Selection and Vetting | `frontend/src/pages/legal/Subprocessors.tsx` |
| `APTS-TP-003` | API Security and Authentication | `app/integrations/security_hub/auth.py` · `app/auth_jwt.py` · `app/auth_mfa.py` |
| `APTS-TP-005` | Provider Incident Response, Breach Notification, and Mid-Engagement Compromise | `app/db.py` · `docs/security/2026-04-20-vercel-incident-response.md` |
| `APTS-TP-006` | Dependency Inventory, Risk Assessment, and Supply Chain Verification | `.github/dependabot.yml` · `pyproject.toml` |
| `APTS-TP-008` | Cloud Security Configuration and Hardening | `app/security/headers.py` · `frontend/vercel.json` |
| `APTS-TP-012` | Client Data Classification Framework | `app/narratives/materialize/pii_linter.py` |
| `APTS-TP-013` | Sensitive Data Discovery and Handling | `app/narratives/materialize/pii_linter.py` |
| `APTS-TP-014` | Data Encryption and Cryptographic Controls | `app/auth_jwt.py` · `app/integrations/github_connect/crypto.py` · `app/security/headers.py` |
| `APTS-TP-018` | Tenant Breach Notification | `docs/security/2026-04-20-vercel-incident-response.md` · `app/email_service.py` |
| `APTS-TP-021` | Foundation Model Disclosure and Capability Baseline | `frontend/src/pages/legal/Privacy.tsx` · `docs/operations/mistral-runbook.md` |
| `APTS-RP-011` | Executive Summary and Risk Overview | `app/engines/reconciliation_pdf.py` |

## Methodology

* The vendored requirements catalog is [`app/integrations/apts/data/apts_requirements.json`](../../app/integrations/apts/data/apts_requirements.json) — a snapshot of [github.com/OWASP/APTS](https://github.com/OWASP/APTS), licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Updates land via `scripts/_refresh_apts_standard.py` on a quarterly cadence.
* The curated evidence map is [`app/integrations/apts/evidence_map.py`](../../app/integrations/apts/evidence_map.py) — every entry names a source module and an article anchor an auditor can grep for. A `satisfied` claim with no module is rejected by the unit tests.
* The conformance engine is pure-functional; same inputs always produce the same report (modulo `generated_at`). See [`app/integrations/apts/conformance.py`](../../app/integrations/apts/conformance.py).
* Tier achievement is cumulative + strict: Tier 2 requires Tier 1 + Tier 2 MUSTs all `satisfied`. A `partial` is never treated as `satisfied`.
* Headline score weights MUSTs 1.0 + SHOULDs 0.5; per level: satisfied 1.0, partial 0.5, gap 0.0.

## Plug-in surface

* **Public API**: `GET /api/v1/apts/conformance/self` — no auth, returns the full report shown above.
* **Per-system**: `GET /api/v1/apts/conformance/system/{audit_result_id}` — JWT-required; setting `persist_evidence=true` writes a snapshot to the tenant's evidence chain.
* **MCP tools** (plugin v2.8): `list_apts_requirements` / `get_apts_requirement` / `get_apts_self_conformance` / `get_apts_system_conformance`.
* **Slash commands**: `/specter:apts-conformance`, `/specter:apts-requirements`.
* **Frontend**: [`/apts-conformance`](../../frontend/src/pages/APTSConformance.tsx) renders the headline score gauge, tier ladder, 8-domain heatmap, and the filterable per-requirement table with click-to-detail rationale + module + test anchors.

---

_OWASP APTS v0.1.0 © OWASP Foundation 2026 · Vendored under CC BY-SA 4.0. This conformance report is a self-assessment; APTS has no certification body. External auditor review is welcomed via a GitHub issue._
