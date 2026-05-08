"""OWASP AI Exchange threat-section snapshot — vendored reference data.

The OWASP AI Exchange (https://owaspai.org/) is a community-maintained
flagship project led by Rob van der Veer. As of 2026-04-27 the AI Exchange
has merged with OpenCRE (https://opencre.org/) to harmonize MITRE ATLAS,
NIST AI RMF, NIST CSF, OWASP Top 10 for LLM Applications, ENISA AI
cybersecurity guidance, BIML, and ETSI ISG SAI into a single coherent
taxonomy. This module vendors a curated subset of AI Exchange threat
sections relevant to the EU AI Act compliance surface.

**Stable IDs caveat**: the harmonized AI Exchange ID scheme is currently
in beta. The IDs below are *our* internal stable handles, paired with the
canonical AI Exchange URL so an auditor can always resolve them to the
upstream definition. When OWASP publishes a v1.0 stable ID scheme we
re-key this module and update :data:`LAST_SYNCED`.

**Vendoring rationale**: same as :mod:`app.data.atlas_techniques` — pinned
snapshot, offline operation, quarterly review cadence over silent drift.

This module is a pure data file — no I/O, no logic.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field, HttpUrl


LAST_SYNCED: Final[str] = "2026-04-27"
"""ISO date of the last manual review against https://owaspai.org/."""

OWASP_AIX_BASE_URL: Final[str] = "https://owaspai.org"
"""Public AI Exchange site — every entry's ``url`` points to a section anchor."""


class OwaspAixThreat(BaseModel):
    """One OWASP AI Exchange threat-section entry."""

    id: str = Field(min_length=4, max_length=32, pattern=r"^AIX-T\d{2}$")
    title: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=64)
    url: HttpUrl
    description: str = Field(min_length=1, max_length=512)


def _x(tid: str, title: str, category: str, anchor: str, description: str) -> OwaspAixThreat:
    """Construct an :class:`OwaspAixThreat` with the canonical anchored URL."""
    return OwaspAixThreat(
        id=tid,
        title=title,
        category=category,
        url=f"{OWASP_AIX_BASE_URL}/#{anchor}",  # type: ignore[arg-type]
        description=description,
    )


OWASP_AIX_THREATS: Final[tuple[OwaspAixThreat, ...]] = (
    # ── General threats (cross-cutting) ─────────────────────────────────
    _x(
        "AIX-T01",
        "Direct prompt injection",
        "Use-time threats",
        "direct-prompt-injection",
        "An attacker crafts user input that instructs an LLM to ignore prior "
        "system instructions and produce attacker-chosen output. Mitigations: "
        "input sanitisation, system-prompt hardening, output validation.",
    ),
    _x(
        "AIX-T02",
        "Indirect prompt injection",
        "Use-time threats",
        "indirect-prompt-injection",
        "An attacker plants instructions in untrusted content (web pages, "
        "documents, emails) that an LLM later retrieves; the LLM then follows "
        "those instructions on the victim's behalf.",
    ),
    _x(
        "AIX-T03",
        "Sensitive information disclosure",
        "Use-time threats",
        "sensitive-info-disclosure",
        "An LLM reveals information from its training data, system prompt, or "
        "prior session that the user is not authorised to see.",
    ),
    _x(
        "AIX-T04",
        "Insecure output handling",
        "Use-time threats",
        "insecure-output-handling",
        "Downstream systems accept LLM output as trusted input (executing it "
        "as code, rendering it as HTML, passing it to a SQL planner) and are "
        "compromised.",
    ),
    _x(
        "AIX-T05",
        "Excessive agency",
        "Use-time threats",
        "excessive-agency",
        "An LLM agent is granted broader permissions or tool access than its "
        "purpose requires, amplifying the impact of any prompt injection.",
    ),
    _x(
        "AIX-T06",
        "Model evasion via adversarial input",
        "Use-time threats",
        "model-evasion",
        "An attacker crafts inputs designed to cause misclassification or "
        "incorrect output — adversarial examples for vision/audio/text models.",
    ),
    _x(
        "AIX-T07",
        "Model extraction / theft",
        "Use-time threats",
        "model-extraction",
        "An attacker repeatedly queries a model to reconstruct its weights or "
        "behaviour, exfiltrating intellectual property.",
    ),
    _x(
        "AIX-T08",
        "Membership / training-data inference",
        "Use-time threats",
        "membership-inference",
        "An attacker determines whether a specific record was in the model's "
        "training data, leaking GDPR-protected information.",
    ),
    _x(
        "AIX-T09",
        "Denial of ML service",
        "Use-time threats",
        "denial-of-ml-service",
        "An attacker submits crafted inputs that consume disproportionate "
        "compute, denying service or driving up cost.",
    ),
    # ── Development-time threats ────────────────────────────────────────
    _x(
        "AIX-T10",
        "Training-data poisoning",
        "Development-time threats",
        "training-data-poisoning",
        "An attacker injects malicious samples into a training corpus to embed "
        "a flaw or backdoor in the resulting model.",
    ),
    _x(
        "AIX-T11",
        "Model supply-chain compromise",
        "Development-time threats",
        "model-supply-chain",
        "Pre-trained weights, datasets, or ML libraries are compromised "
        "upstream and inherited by the victim's model.",
    ),
    _x(
        "AIX-T12",
        "Backdoored model",
        "Development-time threats",
        "backdoored-model",
        "A model is intentionally trained to behave correctly on benign inputs "
        "but produce attacker-controlled output on a hidden trigger.",
    ),
    # ── Misalignment / governance threats ───────────────────────────────
    _x(
        "AIX-T13",
        "Runaway / misaligned behaviour",
        "Misalignment threats",
        "misalignment",
        "A model pursues objectives that diverge from operator intent — "
        "reward hacking, sycophancy, deceptive alignment.",
    ),
    _x(
        "AIX-T14",
        "Bias and unfair output",
        "Misalignment threats",
        "bias",
        "A model produces systematically biased decisions across a protected "
        "attribute, breaching fairness and Art. 10 data-governance obligations.",
    ),
    _x(
        "AIX-T15",
        "Lack of explainability for high-stakes decisions",
        "Misalignment threats",
        "explainability",
        "A high-risk AI system produces decisions that affected persons cannot "
        "understand or contest, breaching Art. 13 transparency.",
    ),
)
"""Curated subset of OWASP AI Exchange threat sections.

The set is not exhaustive — it covers the threats most frequently cited
across MITRE ATLAS, NIST AI RMF, OWASP Top 10 for LLM Applications, and
the EU AI Act's high-risk obligations.
"""


OWASP_AIX_BY_ID: Final[dict[str, OwaspAixThreat]] = {x.id: x for x in OWASP_AIX_THREATS}
"""Lookup index — ``OWASP_AIX_BY_ID["AIX-T01"]`` → :class:`OwaspAixThreat`."""


__all__ = (
    "OwaspAixThreat",
    "OWASP_AIX_THREATS",
    "OWASP_AIX_BY_ID",
    "OWASP_AIX_BASE_URL",
    "LAST_SYNCED",
)
