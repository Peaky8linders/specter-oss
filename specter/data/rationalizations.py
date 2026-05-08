"""Common Rationalizations source of truth for Phase 2 skill-bundle emission.

Each KB dimension has 3-8 excuse/rebuttal pairs used by SkillEmitter to
populate the `## Common Rationalizations` section of dimension SKILL.md
files. Pairs are hand-authored at module level (static data, fast import).

Seeded from docs/superpowers/harvest/rationalizations-source.md (Phase 1)
plus targeted additions for dimensions not covered by the harvest.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RationalizationPair(BaseModel):
    """A single excuse->rebuttal pair for a KB dimension."""

    excuse: str = Field(min_length=1)
    rebuttal: str = Field(min_length=1)
    source: str = Field(
        min_length=1,
        description="Concrete citation: article paragraph, file:line, or commit SHA",
    )
    confidence: Literal["high", "medium", "low"] = "medium"


# Populated from Phase 1 harvest + inferred pairs derived from EU AI Act text,
# KB questions, repo rules, and recent review findings.
DIMENSION_RATIONALIZATIONS: dict[str, list[RationalizationPair]] = {
    # ─── Art. 4 — AI Literacy ──────────────────────────────────────────
    "ai_literacy": [
        RationalizationPair(
            excuse="Our engineers already know how AI works — formal literacy training is redundant.",
            rebuttal=(
                "Art. 4 requires providers and deployers to ensure a sufficient level of AI literacy "
                "for their staff and other persons dealing with the operation and use of the AI system, "
                "tailored to technical knowledge, experience, education and context. Informal "
                "familiarity is not the measurable standard; documented training is."
            ),
            source="Art. 4",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Only the ML team touches the model, so only they need training.",
            rebuttal=(
                "Art. 4 covers 'persons dealing with the operation and use' — that includes operators, "
                "reviewers, escalation handlers, and deployer staff who act on outputs, not just model "
                "builders. Scope the training to every role in the decision loop."
            ),
            source="Art. 4",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We shared an internal deck; that counts as literacy.",
            rebuttal=(
                "A deck without attendance records, assessment, or role-based content mapping is not "
                "evidence. Auditors expect documented curriculum, completion per employee, and "
                "refresh cadence — produce the attestation artefacts."
            ),
            source="Art. 4 + Annex IV item 1",
            confidence="medium",
        ),
        RationalizationPair(
            excuse="Literacy is soft — skipping it won't fail the audit.",
            rebuttal=(
                "Art. 99(4) ties Art. 4 non-compliance to administrative fines up to EUR 15M or 3% of "
                "worldwide turnover. It is not a soft control — it has a direct penalty ladder."
            ),
            source="Art. 99(4) + Art. 4",
            confidence="high",
        ),
    ],
    # ─── Art. 9 — Risk Management ──────────────────────────────────────
    "risk_mgmt": [
        RationalizationPair(
            excuse="This is a low-risk pilot, Art. 9 risk register is overkill.",
            rebuttal=(
                "Art. 9(1) requires a risk management system for every high-risk AI system regardless "
                "of deployment scope. 'Low-risk' is an output of the classifier — run `/classify` first; "
                "'pilot' is not an exemption (review I1 2026-03-17)."
            ),
            source="Art. 9(1) + docs/reviews/fix-deep-code-review-2026-03-17-19-30-00.md I1",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We'll document risks after the implementation stabilizes.",
            rebuttal=(
                "Art. 9(2) defines risk management as a continuous iterative process, planned and run "
                "throughout the entire lifecycle. 'Stable + no risk register' = non-compliant; the "
                "process must exist before the first deployment."
            ),
            source="Art. 9(2)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Our domain experts know the risks; writing them down is bureaucratic.",
            rebuttal=(
                "Art. 11 + Annex IV item 2(c) require documented risk management measures. Tacit "
                "knowledge is not auditable; notified bodies cannot read minds."
            ),
            source="Art. 11 + Annex IV",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We test residual risk once at release — that's enough.",
            rebuttal=(
                "Art. 9(7) mandates testing at any point throughout the development process and in any "
                "event prior to placing on the market or putting into service. Release-only testing "
                "misses risks surfaced by post-training changes."
            ),
            source="Art. 9(7)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Risk to children isn't in our target audience, so I'll skip that review.",
            rebuttal=(
                "Art. 9(9) explicitly requires giving specific consideration to whether the system is "
                "likely to be accessed by or impact persons under 18. 'Not our target audience' is not "
                "the legal test — accessibility and impact are."
            ),
            source="Art. 9(9)",
            confidence="high",
        ),
    ],
    # ─── Art. 10 — Data Governance ─────────────────────────────────────
    "data_gov": [
        RationalizationPair(
            excuse="We use public datasets, so data governance doesn't apply.",
            rebuttal=(
                "Art. 10(2) applies to training, validation and testing data regardless of source. "
                "Public provenance does not exempt the provider from representativeness checks, bias "
                "examination, or data preparation documentation."
            ),
            source="Art. 10(2)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Bias testing on training data would slow us down — we'll do it post-launch.",
            rebuttal=(
                "Art. 10(2)(f)(g) require examination of possible biases and appropriate measures to "
                "detect, prevent and mitigate them as part of data governance — before the system is "
                "placed on the market, not after."
            ),
            source="Art. 10(2)(f)-(g)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Special-category data is only a GDPR concern, not an AI Act concern.",
            rebuttal=(
                "Art. 10(5) explicitly permits processing of special categories of personal data for "
                "bias detection/correction only under strict conditions — meaning the AI Act adds "
                "obligations on top of GDPR rather than deferring to it."
            ),
            source="Art. 10(5)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Representativeness is hand-wavy; let's ship and see.",
            rebuttal=(
                "Art. 10(3) requires training/validation/testing datasets to be relevant, sufficiently "
                "representative, and to the best extent possible free of errors and complete in view "
                "of the intended purpose. 'Hand-wavy' is a product defect, not a compliance posture."
            ),
            source="Art. 10(3)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We don't retain provenance metadata because it inflates storage.",
            rebuttal=(
                "Art. 10(2)(a)-(c) and Annex IV require documentation of data collection processes, "
                "data origin, and preparation operations. Storage cost is not a lawful exception."
            ),
            source="Art. 10(2)(a)-(c) + Annex IV",
            confidence="high",
        ),
    ],
    # ─── Art. 11 — Technical Documentation ─────────────────────────────
    "tech_docs": [
        RationalizationPair(
            excuse="Our README is comprehensive; that covers Annex IV.",
            rebuttal=(
                "Art. 11(1) requires technical documentation drawn up before the system is placed on "
                "the market that demonstrates the system meets Chapter III Section 2 requirements. "
                "Annex IV lists 9 numbered categories (general description, detailed description of "
                "elements, monitoring, standards, declaration, post-market plan, etc.) — a README "
                "rarely hits all 9."
            ),
            source="Art. 11(1) + Annex IV",
            confidence="high",
        ),
        RationalizationPair(
            excuse="I'll let the agent generate the compliance doc — the regulator can sanity-check later.",
            rebuttal=(
                "`examiner_questions.py` is explicitly 'deterministic examiner-question digest — "
                "AuditHive-parity narrative, no LLM'. Regulator-facing text is deterministic by design; "
                "LLM drift in audit narratives is a product defect."
            ),
            source="CLAUDE.md — examiner_questions description",
            confidence="medium",
        ),
        RationalizationPair(
            excuse="Docs were frozen at v1 release — we don't need to rev them for a minor update.",
            rebuttal=(
                "Art. 11(2) and post-market monitoring obligations require documentation to be kept "
                "up-to-date. 'Minor update' does not exempt the provider from revising the Annex IV "
                "package when the system changes."
            ),
            source="Art. 11(2) + Art. 72",
            confidence="high",
        ),
        RationalizationPair(
            excuse="SMEs get a lighter documentation regime — we can skip some sections.",
            rebuttal=(
                "Art. 11(1) last subparagraph allows SMEs to provide Annex IV elements in a simplified "
                "manner using a Commission-provided template — it does not allow skipping categories. "
                "Simplified form, same coverage."
            ),
            source="Art. 11(1) final subpara",
            confidence="high",
        ),
    ],
    # ─── Art. 12 — Record-Keeping / Logging ────────────────────────────
    "logging": [
        RationalizationPair(
            excuse="We log errors to stdout; that's enough for compliance.",
            rebuttal=(
                "Art. 12(1) requires automatic recording of events ('logs') over the lifetime of the "
                "system, enabling traceability of functioning. stdout is volatile; compliance requires "
                "persistence, tamper-resistance, and retrievability."
            ),
            source="Art. 12(1)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Logs pile up — I'll rotate them every 30 days to save disk.",
            rebuttal=(
                "Art. 19(1) requires providers to keep the logs generated by their high-risk AI system "
                "for at least 6 months (unless sector law requires longer). 30-day rotation is "
                "sub-statutory retention."
            ),
            source="Art. 19(1)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We store logs inline in SQLite — immutable storage is a nice-to-have.",
            rebuttal=(
                "Specter's audit chain bucket uses Object Lock Compliance with 10-year retention "
                "precisely because Art. 12 + Art. 18 make the log trail legally binding evidence. "
                "Append-only is a regulatory design constraint, not a feature."
            ),
            source="CLAUDE.md — Deployment/Object Lock + Art. 12",
            confidence="high",
        ),
        RationalizationPair(
            excuse="For biometric categorisation we'll log inputs — outputs contain PII.",
            rebuttal=(
                "Art. 12(2)(a)-(d) enumerate required log categories for high-risk systems used in "
                "biometric identification: period, reference database, input data leading to a match, "
                "identification of natural persons involved in verification. Skipping outputs breaks "
                "the chain the regulator needs for re-examination."
            ),
            source="Art. 12(2)",
            confidence="high",
        ),
    ],
    # ─── Art. 13 & 50 — Transparency ───────────────────────────────────
    "transparency": [
        RationalizationPair(
            excuse="Our UI shows 'Powered by AI' somewhere in the footer — that's transparent enough.",
            rebuttal=(
                "Art. 13(1) requires high-risk AI to be designed so deployers can interpret the "
                "system's output and use it appropriately. Footer disclosure does not satisfy output "
                "interpretability; instructions for use under Art. 13(2)-(3) must accompany it."
            ),
            source="Art. 13(1)-(3)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Chatbot users know they're talking to a bot; formal disclosure is pedantic.",
            rebuttal=(
                "Art. 50(1) requires providers to design AI systems that interact with natural persons "
                "such that the persons concerned are informed they are interacting with an AI — unless "
                "obvious from the circumstances and context. The provider carries the burden of proving "
                "obviousness; assuming it is risky."
            ),
            source="Art. 50(1)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Instructions for use ship as a PDF link — that satisfies Art. 13.",
            rebuttal=(
                "Art. 13(3) enumerates mandatory content for instructions for use: identity of "
                "provider, characteristics and limitations, intended purpose, level of accuracy and "
                "robustness, foreseeable misuse, oversight measures, expected lifetime, etc. A link "
                "alone does not confirm content coverage."
            ),
            source="Art. 13(3)(a)-(f)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We'll handle emotion recognition disclosure at the UI layer later.",
            rebuttal=(
                "Art. 50(3) requires deployers of emotion-recognition or biometric-categorisation "
                "systems to inform natural persons exposed to them of the operation of the system. "
                "'Later' = at time of first exposure, not post-hoc."
            ),
            source="Art. 50(3)",
            confidence="high",
        ),
    ],
    # ─── Art. 14 — Human Oversight ─────────────────────────────────────
    "human_oversight": [
        RationalizationPair(
            excuse="The model is accurate enough that human oversight is just theatre.",
            rebuttal=(
                "Art. 14(1) requires high-risk systems to be designed such that they can be "
                "effectively overseen by natural persons while in use. Accuracy does not substitute "
                "for overseeability — Art. 14(2) lists specific risks (health, safety, fundamental "
                "rights) oversight must address."
            ),
            source="Art. 14(1)-(2)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We added a stop button; Art. 14 is covered.",
            rebuttal=(
                "Art. 14(4)(a)-(e) require five specific abilities for oversight persons: understand "
                "capacities/limitations, remain aware of automation bias, correctly interpret outputs, "
                "decide not to use or disregard outputs, and intervene or halt. One button = one of "
                "five, not five-of-five."
            ),
            source="Art. 14(4)(a)-(e)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Biometric identification matches are 99.9% accurate — a single reviewer is fine.",
            rebuttal=(
                "Art. 14(5) requires that, for systems used for remote biometric identification, no "
                "action or decision is taken by the deployer based on the system's output unless "
                "separately verified and confirmed by at least two natural persons. One reviewer is "
                "sub-statutory."
            ),
            source="Art. 14(5)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="The operator can always override — that's oversight by design.",
            rebuttal=(
                "Art. 14(4)(b) specifically calls out automation bias — the tendency to over-rely on "
                "automated outputs, particularly under time pressure. 'Can always override' without "
                "active debiasing training/workflow is not effective oversight."
            ),
            source="Art. 14(4)(b)",
            confidence="high",
        ),
    ],
    # ─── Art. 15 — Accuracy, Robustness & Cybersecurity ────────────────
    "security": [
        RationalizationPair(
            excuse="Our cloud provider's WAF already blocks OWASP Top 10 — we're covered.",
            rebuttal=(
                "Art. 15(5) requires high-risk AI systems to be resilient against attempts by "
                "unauthorised third parties to alter their use, outputs or performance by exploiting "
                "system vulnerabilities — including data poisoning, model poisoning, and adversarial "
                "examples. WAFs do not address those AI-specific threat vectors."
            ),
            source="Art. 15(5)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Accuracy metrics are on the dashboard — no need to declare them in the instructions.",
            rebuttal=(
                "Art. 15(3) + Art. 13(3)(b)(ii) require levels of accuracy, including relevant metrics, "
                "to be declared in the accompanying instructions for use. Dashboards are internal; "
                "instructions are the regulator-facing contract."
            ),
            source="Art. 15(3) + Art. 13(3)(b)(ii)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Feedback loops are fine — retraining on user corrections just improves the model.",
            rebuttal=(
                "Art. 15(4) explicitly requires technical and organisational measures to mitigate "
                "feedback loops that may bias outputs when AI systems continue to learn after being "
                "put into service. Unmitigated online learning is a named risk, not a feature."
            ),
            source="Art. 15(4)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Scores below zero are a rounding artifact — I'll ignore them.",
            rebuttal=(
                "Commit 0605d98 + 002b7c8 added a regression test for non-negative compliance_scores "
                "after negative values shipped. Clamp at the engine, not at the UI. Accuracy metrics "
                "reported under Art. 15(3) must be sound at source."
            ),
            source="git log 0605d98, 002b7c8",
            confidence="high",
        ),
    ],
    # ─── Art. 43, 47, 48 — Conformity Assessment ───────────────────────
    "conformity_assessment": [
        RationalizationPair(
            excuse="Self-assessment via internal control is faster; we'll take that route for all systems.",
            rebuttal=(
                "Art. 43(1) ties the assessment procedure to the Annex III category. For Annex III "
                "point 1 (biometrics) providers without harmonised standards MUST use a notified body "
                "(Annex VII). Internal control (Annex VI) is not universally available."
            ),
            source="Art. 43(1) + Annex VI/VII",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We have the EU declaration of conformity in email — that's on file.",
            rebuttal=(
                "Art. 47(1) requires the declaration to be drawn up in a written machine-readable, "
                "physical or electronically signed form, to state the information listed in Annex V, "
                "and to be kept at the disposal of national competent authorities for 10 years. "
                "'In email' is not equivalent to the statutory artefact."
            ),
            source="Art. 47(1) + Annex V",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We'll CE-mark the system after launch once we have user numbers.",
            rebuttal=(
                "Art. 48(1)-(2) require the CE marking to be affixed before the system is placed on "
                "the market or put into service, visibly, legibly and indelibly. Post-launch marking "
                "is a direct Art. 48 breach."
            ),
            source="Art. 48(1)-(2)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Minor retraining after launch doesn't change conformity — no need to repeat.",
            rebuttal=(
                "Art. 43(4) requires a new conformity assessment procedure whenever a high-risk AI "
                "system is substantially modified. 'Substantial' is defined in Art. 3(23) — it is not "
                "a self-serving judgement; assess against the definition."
            ),
            source="Art. 43(4) + Art. 3(23)",
            confidence="high",
        ),
    ],
    # ─── Art. 17 — Quality Management System ───────────────────────────
    "quality_management": [
        RationalizationPair(
            excuse="We follow ISO 9001 — Art. 17 QMS is automatically satisfied.",
            rebuttal=(
                "Art. 17(1) enumerates 13 specific QMS elements (compliance strategy, techniques and "
                "procedures for design, examination, testing, data management, risk management, "
                "post-market monitoring, incident reporting, resource management, etc.) aligned with "
                "but not subsumed by ISO 9001. Map every element explicitly."
            ),
            source="Art. 17(1)(a)-(m)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Our QMS is on a SharePoint page — that's proportionate for our size.",
            rebuttal=(
                "Art. 17(2) allows proportionality to the size of the provider's organisation but "
                "still requires systematic and orderly documented policies, procedures and "
                "instructions. A wiki page without versioning/review records is below the floor, "
                "regardless of company size."
            ),
            source="Art. 17(2)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Post-market monitoring is sales's problem — not the QMS's.",
            rebuttal=(
                "Art. 17(1)(h) places the setting-up, implementation, and maintenance of a "
                "post-market monitoring system inside the QMS. Operationally it may be a separate "
                "team; contractually it is a QMS deliverable."
            ),
            source="Art. 17(1)(h) + Art. 72",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Financial-sector providers can swap their existing QMS for Art. 17 without changes.",
            rebuttal=(
                "Art. 17(3)-(4) permit compliance via sector-specific internal governance "
                "arrangements (e.g., CRD) but require providers to still meet the Art. 17 elements. "
                "It is a credit for existing coverage, not a waiver."
            ),
            source="Art. 17(3)-(4)",
            confidence="high",
        ),
    ],
    # ─── Art. 26 & 27 — Deployer Obligations ───────────────────────────
    "deployer_obligations": [
        RationalizationPair(
            excuse="We're only the deployer — provider obligations don't apply to us.",
            rebuttal=(
                "Art. 25(1) turns a deployer into a provider when they (a) put their name/trademark "
                "on an existing high-risk system, (b) make a substantial modification, or (c) modify "
                "intended purpose such that it becomes high-risk. Deployer status is not a stable "
                "label — verify against Art. 25 every release."
            ),
            source="Art. 25(1)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We trust the provider's instructions — no internal oversight process needed.",
            rebuttal=(
                "Art. 26(1) requires deployers to take appropriate technical and organisational "
                "measures to ensure they use such systems in accordance with the instructions for "
                "use. 'Trust' is not a technical measure; documented oversight and training are."
            ),
            source="Art. 26(1)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="FRIA is optional for small deployers.",
            rebuttal=(
                "Art. 27(1) requires a Fundamental Rights Impact Assessment from deployers that are "
                "bodies governed by public law, private entities providing public services, or that "
                "deploy Annex III point 5(b)/(c) systems. It is role-based, not size-based. "
                "Review I2 on 2026-03-17 also caught authorized-representatives being mis-classified "
                "as deployers — verify role first."
            ),
            source="Art. 27(1) + docs/reviews/fix-deep-code-review-2026-03-17-19-30-00.md I2",
            confidence="high",
        ),
        RationalizationPair(
            excuse="If our deployer uses a system for something we didn't intend, that's their problem.",
            rebuttal=(
                "Art. 26(6) obliges the deployer to inform the provider of any serious incident and "
                "Art. 72 obliges the provider to investigate. Intended purpose drift is shared "
                "liability, not buck-passing."
            ),
            source="Art. 26(6) + Art. 72",
            confidence="high",
        ),
    ],
    # ─── Art. 50(2-4) — Content Transparency / Synthetic Media ─────────
    "content_transparency": [
        RationalizationPair(
            excuse="Watermarking generated content breaks our UX — we'll disclose in text instead.",
            rebuttal=(
                "Art. 50(2) requires providers of generative AI systems to ensure outputs are marked "
                "in a machine-readable format and detectable as artificially generated or manipulated "
                "— using techniques like watermarks, metadata identifications, cryptographic methods. "
                "Text disclosure is not machine-readable."
            ),
            source="Art. 50(2)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We only produce deepfakes for entertainment — Art. 50(4) exemption applies.",
            rebuttal=(
                "Art. 50(4) second subpara allows adaptation of disclosure to 'evident artistic, "
                "creative, satirical, fictional or analogous work' BUT still requires transparency — "
                "only the form is adapted, not the fact. Blanket entertainment exemption does not "
                "exist."
            ),
            source="Art. 50(4)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Our AI just translates text — it's not generative, so Art. 50(2) is out of scope.",
            rebuttal=(
                "Art. 50(2) covers 'AI systems generating synthetic audio, image, video or text "
                "content'. Translation systems generate text; the regulator reads this broadly. If in "
                "doubt, mark."
            ),
            source="Art. 50(2)",
            confidence="medium",
        ),
        RationalizationPair(
            excuse="Our text editor is 'standard' so Art. 50(4) disclosure doesn't apply.",
            rebuttal=(
                "Art. 50(4) last subpara's 'standard editing' carve-out is narrow: text AI-generated/"
                "manipulated on matters of public interest must still be disclosed unless the "
                "AI-generated content has undergone a process of human review or editorial control "
                "and a natural or legal person holds editorial responsibility for publication."
            ),
            source="Art. 50(4) final subpara",
            confidence="high",
        ),
    ],
    # ─── Art. 53 — GPAI Model Obligations ──────────────────────────────
    "gpai": [
        RationalizationPair(
            excuse="Open-weight release means we're exempt from GPAI obligations.",
            rebuttal=(
                "Art. 53(2) provides a partial exemption for free and open-source GPAI models from "
                "Art. 53(1)(a)-(b) technical documentation AND downstream-provider information — but "
                "NOT from copyright policy (Art. 53(1)(c)) or training-data summary (Art. 53(1)(d)), "
                "and NOT from Art. 55 systemic-risk obligations."
            ),
            source="Art. 53(2)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Our training data summary can just say 'diverse public sources'.",
            rebuttal=(
                "Art. 53(1)(d) requires a sufficiently detailed summary of the content used for "
                "training, according to a template provided by the AI Office. 'Diverse public sources' "
                "is not sufficiently detailed; the template will be enforced."
            ),
            source="Art. 53(1)(d)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Downstream providers build on us — they can ask support for technical info.",
            rebuttal=(
                "Art. 53(1)(b) requires GPAI providers to proactively draw up and keep up-to-date "
                "information and documentation, and make it available to downstream providers that "
                "integrate the model. Annex XII lists the minimum content. Ad-hoc support channels "
                "do not replace the documented artefact."
            ),
            source="Art. 53(1)(b) + Annex XII",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We don't need to police copyright — downstream users are responsible.",
            rebuttal=(
                "Art. 53(1)(c) places the obligation to put in place a policy to comply with Union "
                "copyright law, in particular to identify and comply with reservations of rights under "
                "Art. 4(3) of Directive (EU) 2019/790, on the GPAI provider. Not on the downstream."
            ),
            source="Art. 53(1)(c)",
            confidence="high",
        ),
    ],
    # ─── Art. 51 & 55 — GPAI Systemic Risk ─────────────────────────────
    "gpai_systemic_risk": [
        RationalizationPair(
            excuse="Our training compute is below 10^25 FLOP — Art. 51 doesn't concern us.",
            rebuttal=(
                "Art. 51(1)(a) presumes systemic risk when cumulative compute used for training is "
                "greater than 10^25 FLOPs, but Art. 51(1)(b) + (2) allow the Commission to designate "
                "GPAI models as having systemic risk based on other capability criteria listed in "
                "Annex XIII. Sub-threshold FLOP does not equal exemption."
            ),
            source="Art. 51(1)-(2) + Annex XIII",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Designation is the Commission's job; we'll wait for notification.",
            rebuttal=(
                "Art. 52(1) obliges the provider to notify the Commission without delay and in any "
                "event within two weeks of meeting the Art. 51(1)(a) threshold — before any "
                "Commission designation. Waiting is a direct Art. 52 breach."
            ),
            source="Art. 52(1)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Cybersecurity protections are the deployer's job — we just ship weights.",
            rebuttal=(
                "Art. 55(1)(d) requires providers of GPAI models with systemic risk to ensure an "
                "adequate level of cybersecurity protection for the model and its physical "
                "infrastructure. Review I4 2026-03-17: do not confuse cop-sec1 (Cybersecurity) with "
                "gs-1 (FLOP threshold)."
            ),
            source="Art. 55(1)(d) + docs/reviews/fix-deep-code-review-2026-03-17-19-30-00.md I4",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Model evaluations are a release formality — we already red-team internally.",
            rebuttal=(
                "Art. 55(1)(a)-(b) require state-of-the-art model evaluations, including adversarial "
                "testing, to identify and mitigate systemic risks — and serious-incident tracking. "
                "Internal red-teaming is one input; documented evaluation and incident documentation "
                "are the deliverables."
            ),
            source="Art. 55(1)(a)-(b)",
            confidence="high",
        ),
    ],
    # ─── Art. 9/14/15/72 — Decision Governance ─────────────────────────
    "decision_governance": [
        RationalizationPair(
            excuse="We log decisions; governance reviews can happen on demand.",
            rebuttal=(
                "Art. 9 + Art. 14 + Art. 72 combine to require a documented governance workflow "
                "(approve/block/escalate) with oversight signals captured in the audit chain. "
                "'On demand' gives no evidence that oversight happened in-time."
            ),
            source="Art. 9 + Art. 14 + Art. 72",
            confidence="high",
        ),
        RationalizationPair(
            excuse="The model only outputs a recommendation — humans decide, so governance is trivial.",
            rebuttal=(
                "Art. 14(4)(b) names automation bias as a first-class risk: people over-rely on "
                "'recommendations', especially under time pressure. Governance must include "
                "debiasing measures (rotating reviewers, hold-times, disagreement logging)."
            ),
            source="Art. 14(4)(b)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Serious incident reporting is rare — we'll react when one happens.",
            rebuttal=(
                "Art. 73(1) requires providers to report serious incidents to market surveillance "
                "authorities of the Member States where the incident occurred, and to do so "
                "immediately after establishing a causal link (and at most within the timeframes in "
                "Art. 73(2)-(4): as short as 2 days for widespread infringements). 'React when it "
                "happens' without a pre-wired pipeline blows the clock."
            ),
            source="Art. 73(1)-(4)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Escalation paths are documented in Confluence — that's our governance.",
            rebuttal=(
                "Art. 72(1) requires post-market monitoring to be proportionate and systematic, with "
                "a plan forming part of the technical documentation under Annex IV point 6. Wikis "
                "without change history or execution records are not Annex-IV-grade governance."
            ),
            source="Art. 72(1) + Annex IV point 6",
            confidence="high",
        ),
    ],
    # ─── Art. 15 / ISO 27002 — Access Control & Identity ───────────────
    "access_control": [
        RationalizationPair(
            excuse="This endpoint works the same for every user — I don't need a tenant scope.",
            rebuttal=(
                "Review C3 main-2026-04-15 (cross-tenant IDOR on /v1/provenance/*): authenticated "
                "users retrieved other tenants' evidence because no owner_id scoping existed. Every "
                "route returning stored data must scope to the caller. This is also Art. 15(5) "
                "'unauthorised access' mitigation."
            ),
            source="docs/reviews/main-session-2026-04-15-deep-review.md C3 + Art. 15(5)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="I'll return the decrypted auth header so the UI can show 'Bearer ...'.",
            rebuttal=(
                "Review C5 2026-04-14: list_by_user returned plaintext bearer tokens in HTTP "
                "responses — cache layers, proxies, browser dev tools all exposed them. API responses "
                "must redact secrets (*** or last-4-chars); decryption only inside the execution loop."
            ),
            source="docs/reviews/antifragile-hardening-2026-04-14-09-30-00.md C5",
            confidence="high",
        ),
        RationalizationPair(
            excuse="If the encryption key env var is missing, I'll fall back to JWT_SECRET_KEY.",
            rebuttal=(
                "Review C8 2026-04-14: the fallback chain ended at the literal "
                "'dev-secret-key-not-for-production', making stored tokens trivially decryptable. "
                "Add a startup check that halts if P2P_TESTING is unset AND the encryption key is "
                "empty."
            ),
            source="docs/reviews/antifragile-hardening-2026-04-14-09-30-00.md C8",
            confidence="high",
        ),
        RationalizationPair(
            excuse="P2P_AUTH_ENABLED=0 is fine for staging — real JWT is only needed in prod.",
            rebuttal=(
                "Commit 7a28549 removed that bypass precisely because staging-only toggles leak into "
                "prod. VITE_AUTH_BYPASS is frontend-dev-only; backend auth is unconditional."
            ),
            source="git log 7a28549 + CLAUDE.md Project Overview",
            confidence="high",
        ),
        RationalizationPair(
            excuse="I'll accept a --password CLI flag — it's a script for admins only.",
            rebuttal=(
                "Review I6 2026-04-15: --password leaks to /proc/<pid>/cmdline and ps aux. Use "
                "getpass.getpass() or a designated env var, never a CLI arg."
            ),
            source="docs/reviews/main-session-2026-04-15-deep-review.md I6",
            confidence="high",
        ),
    ],
    # ─── Art. 15 / NIST SP 800-53 — Infrastructure & MLOps Security ────
    "infra_mlops": [
        RationalizationPair(
            excuse="The URI builder only accepts strings I control — no need to percent-encode.",
            rebuttal=(
                "Review C1 2026-04-15: PROV-O URI builders interpolated created_by (attacker-"
                "writable via store.record) into URIRef(f'...#evidence/{x}'), producing Turtle "
                "injection. Always urllib.parse.quote(x, safe='') for any caller-supplied URI "
                "component."
            ),
            source="docs/reviews/main-session-2026-04-15-deep-review.md C1",
            confidence="high",
        ),
        RationalizationPair(
            excuse="The `endpoint` field is just a URL — users won't put internal IPs there.",
            rebuttal=(
                "Review C7 2026-04-14: create_campaign_schedule skipped _validate_scan_endpoint, "
                "allowing schedules pointing at http://169.254.169.254/... (cloud IAM metadata). "
                "SSRF validation must run on every endpoint-accepting route, not just live-scan."
            ),
            source="docs/reviews/antifragile-hardening-2026-04-14-09-30-00.md C7",
            confidence="high",
        ),
        RationalizationPair(
            excuse="The 500 will be obvious from the stack trace — I don't need to sanitize.",
            rebuttal=(
                "Error responses must not leak internal details (stack traces, file paths, config "
                "values). Review I8 2026-04-15 caught raw g.serialize() 500s leaking stack traces on "
                "/v1/provenance/*. Also Art. 15(5) resilience against 'attempts to alter use or "
                "outputs' covers information leakage."
            ),
            source=".claude/rules/api-rules.md:5 + docs/reviews/main-session-2026-04-15-deep-review.md I8",
            confidence="high",
        ),
        RationalizationPair(
            excuse="The newest-first list is fine — the function doesn't care about order.",
            rebuttal=(
                "Review C6 2026-04-14: _compute_novel_vulnerability_rate was docstring-specified as "
                "oldest-first; passing newest-first inverted the signal so systems closing gaps "
                "scored as accumulating novelty. Read the docstring; don't guess ordering."
            ),
            source="docs/reviews/antifragile-hardening-2026-04-14-09-30-00.md C6",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Logs are in SQLite — we can always delete the bad row later.",
            rebuttal=(
                "specter-audit-chain uses Object Lock Compliance with 10-year retention (Art. 18). "
                "Append-only is a regulatory design constraint — 'just delete the bad row' is "
                "non-compliant by construction."
            ),
            source="CLAUDE.md — Deployment/Object Lock + Art. 18",
            confidence="high",
        ),
    ],
    # ─── Art. 15 / NIST SP 800-161 — Supply Chain & Third-Party Risk ───
    "supply_chain": [
        RationalizationPair(
            excuse="`pip-audit || true` keeps the build green while we investigate.",
            rebuttal=(
                "Review I10 2026-04-15: || true made the dependency scan a no-op — vulnerable builds "
                "shipped to Railway without alerting. Supply-chain gates must block merges, not "
                "decorate them."
            ),
            source="docs/reviews/main-session-2026-04-15-deep-review.md I10",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Upstream GPAI provider is responsible for their model — we ship downstream.",
            rebuttal=(
                "Art. 25(4) requires the downstream provider of a high-risk system to have written "
                "agreement with the upstream GPAI provider, covering information, capabilities, "
                "technical access and documentation necessary for Chapter III Section 2 compliance. "
                "'They handle it' is contractual negligence."
            ),
            source="Art. 25(4)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We pin versions; that's sufficient supply-chain hygiene.",
            rebuttal=(
                "Art. 15(4)-(5) resilience requires protection against data-poisoning and "
                "model-poisoning. Pinning guards against unintentional drift, not intentional "
                "compromise of pinned artefacts — add SBOM, signature verification, and provenance "
                "on top."
            ),
            source="Art. 15(4)-(5)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Third-party datasets come with licence files — that covers data governance.",
            rebuttal=(
                "Art. 10(2)-(3) require representativeness, bias examination, preparation "
                "documentation regardless of source. A licence file says you may use the data; it "
                "says nothing about fitness for the intended purpose."
            ),
            source="Art. 10(2)-(3)",
            confidence="high",
        ),
    ],
    # ─── Art. 95 — Voluntary Codes of Conduct ──────────────────────────
    "voluntary_codes": [
        RationalizationPair(
            excuse="We're not high-risk — codes of conduct don't matter.",
            rebuttal=(
                "Art. 95(1) encourages providers of non-high-risk AI systems to adopt voluntary codes "
                "applying mutatis mutandis the Chapter III Section 2 requirements. 'Don't matter' "
                "ignores the bridge the regulator built from non-high-risk to high-risk practices."
            ),
            source="Art. 95(1)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Signing a code is PR — no operational impact.",
            rebuttal=(
                "Art. 95(2)(a)-(e) enumerate specific objectives codes may contribute to (environmental "
                "sustainability, AI literacy, inclusive and diverse design, impact on vulnerable "
                "persons, stakeholder participation). Once adopted, commitments become "
                "audit-checkable."
            ),
            source="Art. 95(2)(a)-(e)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Freemium will get us more funnel.",
            rebuttal=(
                "GTM Playbook: 'Freemium and bootstrapped can be a lethal combination' (Roeder). No "
                "free tier — point tire-kickers to the EC's free compliance checker. 14-day trial "
                "only. Aligning GTM with voluntary-code posture avoids greenwashing claims."
            ),
            source="docs/GTM_BOOTSTRAP_PLAYBOOK.md:40-58",
            confidence="medium",
        ),
        RationalizationPair(
            excuse="Voluntary code compliance is hand-wavy — tracking it isn't engineering's job.",
            rebuttal=(
                "Art. 95(4) tasks the AI Office and Member States with taking into account specific "
                "interests and needs of SMEs including start-ups — implying measurable adherence to "
                "codes becomes a form of compliance evidence. Track commitments like obligations."
            ),
            source="Art. 95(4)",
            confidence="medium",
        ),
    ],

    # ─── Agent-aware rationalizations (Nannini et al. 2026) ─────────────
    "agent_inventory": [
        RationalizationPair(
            excuse="The architecture diagram is the inventory — we don't need a separate document.",
            rebuttal=(
                "Per Nannini et al. Conclusion 3, the inventory tracks external actions, data "
                "flows, connected systems, and affected persons — not internal architecture. The "
                "diagram tells you how the agent is built; the inventory tells you what it can "
                "DO and to WHOM. Different artefact, different purpose."
            ),
            source="paper §3 + Conclusion 3 (line 2456)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We're a general-purpose platform — we can't predict what deployers will do.",
            rebuttal=(
                "The paper §3 (lines 354-365) frames this as a structural classification dilemma: "
                "either restrict the intended purpose contractually + technically, or design for "
                "the most demanding regulatory tier under Article 3(13). Either way the "
                "platform-level inventory of *capabilities* is the auditor's starting point."
            ),
            source="paper §3 (lines 354-365), Art. 3(13) + Art. 25(4)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Inventories drift the moment they're written — they're not worth maintaining.",
            rebuttal=(
                "Drift is the point. A versioned inventory is what makes substantial-modification "
                "review (Art. 3(23)) possible. If the inventory is current, you can answer 'what "
                "changed since the last conformity assessment?' If it isn't, you can't claim "
                "post-market control."
            ),
            source="Art. 3(23) + paper §6.4",
            confidence="medium",
        ),
    ],

    "tool_governance": [
        RationalizationPair(
            excuse="The system prompt tells the model not to delete files — that's our safeguard.",
            rebuttal=(
                "Per paper §6.1 (line 728): a system prompt 'do not delete files' is not a "
                "security control — it's a natural-language suggestion. Article 15(4) requires "
                "the inability to perform a restricted action be enforced at the API level, "
                "where the tool simply isn't exposed."
            ),
            source="paper §6.1 (line 728), Art. 15(4)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Each tool has its own permissions — we don't need a central registry.",
            rebuttal=(
                "Kim et al. (USENIX Security 2026) document cross-tool propagation: a compromise "
                "in one tool cascades through the agent's action chain, and per-tool permissions "
                "don't compose. The central registry plus default-deny is what stops authority "
                "escalation through legitimately-granted scopes."
            ),
            source="paper §6.1 (line 750), Kim et al.",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Static service-account credentials are easier to manage than JIT — and just as safe.",
            rebuttal=(
                "Static credentials cannot be governed by traditional IAM at agent scale (paper "
                "§6.1 NHI thesis, line 760): a single agent holds CRM+email+cloud+payment "
                "credentials simultaneously. JIT issuance per action with short TTLs is what the "
                "paper names as the minimum architectural posture."
            ),
            source="paper §6.1 (line 760)",
            confidence="medium",
        ),
    ],

    "chain_transparency": [
        RationalizationPair(
            excuse="Each agent logs its own decisions — that's enough for traceability.",
            rebuttal=(
                "Per paper §6.3, transparency obligations propagate to every affected party in "
                "the action chain. Per-agent logs without parent_decision_id can't answer 'show "
                "me the trace from user prompt to the database write that affected this data "
                "subject' — which is the auditor's question."
            ),
            source="paper §6.3, Art. 12 + 13 + 50",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Our agent_id is a UUID — we don't need cryptographic signing.",
            rebuttal=(
                "Shapira et al.'s red-team finding (paper §6.3, lines 888-890) showed agents "
                "spoof self-asserted identity. A UUID is a string the caller supplies — a "
                "compromised agent can write any value. Cryptographic signing on the write path "
                "is the minimum the paper requires."
            ),
            source="paper §6.3 (lines 888-890), Shapira et al.",
            confidence="high",
        ),
        RationalizationPair(
            excuse="C2PA marking is for image generators — we ship a text agent.",
            rebuttal=(
                "Art. 50(2) covers all synthetic content — text, audio, image, video — when made "
                "available to the public. Marking via metadata header or AI-disclosure prefix "
                "is required at the boundary where the agent's output leaves the system through "
                "a tool call (email send, social post)."
            ),
            source="Art. 50(2)",
            confidence="medium",
        ),
    ],

    "runtime_drift": [
        RationalizationPair(
            excuse="We use `gpt-4o` — OpenAI handles version pinning behind the scenes.",
            rebuttal=(
                "OpenAI rolls snapshots silently behind the floating alias. Per paper §6.4 "
                "Conclusion 8 (line 2470), if you can't demonstrate the system stayed inside "
                "the conformity-assessment envelope, the system fails Articles 12 / 14 / 15 / "
                "43 / 72. Pin to a dated snapshot or stamp the served snapshot in the evidence "
                "chain on every call."
            ),
            source="paper §6.4 + Conclusion 8 (line 2470)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Drift detection is a future problem — it'll be in v2.",
            rebuttal=(
                "Per paper Conclusion 4 (line 2459): 'Versioned runtime state, continuous "
                "behavioral monitoring, and automated drift detection are minimum engineering "
                "requirements, not optional enhancements.' Without these, a high-risk agent "
                "system 'cannot currently be placed on the EU market consistent with the "
                "essential requirements.'"
            ),
            source="paper Conclusion 4 + 8 (lines 2459, 2470)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="Substantial-modification is a legal interpretation question — engineering can wait.",
            rebuttal=(
                "Art. 3(23) defines the threshold but Art. 96(1)(c) guidance has not been "
                "published (paper §9 observation 8, line 2014). Until guidance arrives, providers "
                "must make their own interpretive judgments and *document them*. Without a "
                "written procedure, the operator cannot demonstrate good-faith control."
            ),
            source="Art. 3(23) + Art. 96(1)(c) + paper §9 obs 8",
            confidence="medium",
        ),
    ],

    "regulatory_perimeter": [
        RationalizationPair(
            excuse="The EU AI Act is our primary regulator — the others are out of scope.",
            rebuttal=(
                "Per paper Conclusion 1 (line 2440): 'Parallel compliance across multiple "
                "instruments is not a risk scenario; it is the baseline.' At least eight EU "
                "instruments may apply simultaneously: GDPR, CRA, DSA, Data Act, DGA, NIS2, "
                "sectoral, PLD. Treating them as out-of-scope means missing obligations the "
                "AI Act itself doesn't list."
            ),
            source="paper Conclusion 1 (line 2440)",
            confidence="high",
        ),
        RationalizationPair(
            excuse="We ship the agent as SaaS — CRA only covers shrink-wrapped products.",
            rebuttal=(
                "CRA covers products with digital elements that are placed on the EU market. The "
                "paper Table 5 CRA row explicitly names 'standalone software (VS Code extension, "
                "CLI tool) with network connection' as in-scope. SaaS distribution does not "
                "categorically exempt — the test is whether the product is placed on the market "
                "with network connectivity."
            ),
            source="paper Table 5 CRA row + §7.5",
            confidence="medium",
        ),
        RationalizationPair(
            excuse="Mapping every legislative trigger is a lawyer's job, not an engineer's.",
            rebuttal=(
                "Per paper Step 9 (line 1727), the four-question tool trace (PII / connected "
                "product / platform / sectoral) is engineering work — it's mechanical given the "
                "tool inventory. The output (`adjacent-legislation.md`) is an artefact the "
                "auditor expects from the operator, not a brief the operator outsources."
            ),
            source="paper §8 Step 9 (line 1727)",
            confidence="high",
        ),
    ],
}
