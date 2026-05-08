# Annex IV — APTS Conformance Section (reference self-scan)

**Section anchor**: Art. 15 (accuracy, robustness, cybersecurity) — OWASP APTS
**Section status**: partial

---

**Standard:** OWASP APTS — Autonomous Penetration Testing Standard v0.1.0 (CC BY-SA 4.0).

**Headline conformance:** 61.3%

**Counts:** 26 satisfied · 13 partial · 14 gap · 0 not assessed (of 53 mapped requirements).

**Per-domain coverage:**
- Human Oversight: 100.0%
- Manipulation Resistance: 88.9%
- Safety Controls: 83.3%
- Reporting: 70.0%
- Auditability: 65.0%
- Graduated Autonomy: 50.0%
- Scope Enforcement: 50.0%
- Supply Chain Trust: 22.7%

**Satisfied controls (top 8):**
- `APTS-AR-001` Structured Event Logging with Schema Validation
- `APTS-AR-002` State Transition Logging
- `APTS-AR-008` Context-Aware Decision Logging
- `APTS-AR-010` Cryptographic Hashing of All Evidence
- `APTS-AR-012` Tamper-Evident Logging with Hash Chains
- `APTS-AR-015` Evidence Classification and Sensitive Data Handling
- `APTS-HO-001` Mandatory Pre-Approval Gates for Autonomy Levels L1 and L2
- `APTS-HO-002` Real-Time Monitoring and Intervention Capability
... and 18 more.

**Gap controls requiring remediation (top 8):**
- `APTS-AR-016` Platform Integrity and Supply Chain Attestation
- `APTS-AR-017` Safety Control Regression Testing After Platform Updates
- `APTS-AR-019` AI/ML Model Change Tracking and Drift Detection
- `APTS-SE-007` Dynamic Scope Monitoring and Drift Detection
- `APTS-SE-020` Deployment-Triggered Testing Governance
- `APTS-SE-024` Cloud-Native and Ephemeral Infrastructure Governance
- `APTS-TP-002` Model Version Pinning and Change Management
- `APTS-TP-006` Dependency Inventory, Risk Assessment, and Supply Chain Verification
... and 6 more.

**Methodology:** Each Code Scanner analyzer maps to the APTS requirements it can speak to (see `app/integrations/apts/scanner_mapping.py`); a per-requirement verdict combines the analyzer score (≥80 satisfied · 50-79 partial · <50 gap) with gap-finding counts. When multiple analyzers contribute to one requirement, the worst level wins.

**Source:** automated derivation from the reference apts module scan; OWASP/APTS catalog vendored under CC BY-SA 4.0.
