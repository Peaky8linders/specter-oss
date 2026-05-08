"""MITRE ATLAS technique snapshot — vendored reference data.

ATLAS (Adversarial Threat Landscape for Artificial-Intelligence Systems) is
maintained by MITRE at https://atlas.mitre.org/. This module vendors a curated
subset of techniques relevant to the EU AI Act compliance surface (LLM
prompt injection, data poisoning, model evasion, exfiltration, denial of ML
service, supply-chain compromise).

**Vendoring rationale**: ATLAS is an evolving public taxonomy. We embed a
pinned snapshot rather than fetching live so:

1. Customer-facing artifacts (Compliance Gap Report, evidence chain) carry
   stable IDs across deploys.
2. The integration runs offline and in air-gapped customer deployments.
3. We have a clear quarterly review cadence rather than silent drift.

**Upgrade path**: replace the entries below with a fresh curated subset and
update :data:`LAST_SYNCED`. Run ``pytest -k TestAtlasTechniquesData`` to
catch URL/ID/duplicate regressions.

This module is a pure data file — no I/O, no logic. Imports only stdlib types.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field, HttpUrl

LAST_SYNCED: Final[str] = "2026-04-27"
"""ISO date of the last manual review against https://atlas.mitre.org/."""

ATLAS_BASE_URL: Final[str] = "https://atlas.mitre.org/techniques"
"""Public ATLAS browse URL — every technique has a page at ``{base}/{id}``."""


class AtlasTechnique(BaseModel):
    """One MITRE ATLAS technique entry."""

    id: str = Field(min_length=4, max_length=32, pattern=r"^AML\.T\d{4}(\.\d{3})?$")
    name: str = Field(min_length=1, max_length=128)
    tactic: str = Field(min_length=1, max_length=64)
    url: HttpUrl
    description: str = Field(min_length=1, max_length=512)


def _t(tid: str, name: str, tactic: str, description: str) -> AtlasTechnique:
    """Construct an :class:`AtlasTechnique` with the canonical URL."""
    return AtlasTechnique(
        id=tid,
        name=name,
        tactic=tactic,
        url=f"{ATLAS_BASE_URL}/{tid}",  # type: ignore[arg-type]
        description=description,
    )


ATLAS_TECHNIQUES: Final[tuple[AtlasTechnique, ...]] = (
    # ── Reconnaissance ──────────────────────────────────────────────────
    _t(
        "AML.T0006",
        "Active Scanning",
        "Reconnaissance",
        "Adversaries probe a victim ML system to gather information about its "
        "structure, capabilities, or supporting infrastructure prior to attack.",
    ),
    # ── Resource Development ────────────────────────────────────────────
    _t(
        "AML.T0017",
        "Develop Capabilities",
        "Resource Development",
        "Adversaries build the offensive capabilities (adversarial examples, "
        "poisoned datasets, prompt-injection corpora) that they will later "
        "deploy against the victim ML system.",
    ),
    _t(
        "AML.T0018",
        "Backdoor ML Model",
        "Resource Development",
        "Adversaries train or modify an ML model to embed a backdoor that "
        "activates on a specific trigger pattern, while behaving normally on "
        "other inputs.",
    ),
    _t(
        "AML.T0019",
        "Publish Poisoned Datasets",
        "Resource Development",
        "Adversaries publish poisoned datasets on public hubs so downstream "
        "victims unwittingly fine-tune on them.",
    ),
    # ── Initial Access ──────────────────────────────────────────────────
    _t(
        "AML.T0010",
        "ML Supply Chain Compromise",
        "Initial Access",
        "Adversaries compromise an ML supply-chain component (pre-trained "
        "weights, training data, ML library) to gain initial access to the "
        "victim system.",
    ),
    _t(
        "AML.T0049",
        "Exploit Public-Facing Application",
        "Initial Access",
        "Adversaries exploit a vulnerability in an internet-facing application "
        "(an inference endpoint, a model-serving API) to gain access.",
    ),
    _t(
        "AML.T0051",
        "LLM Prompt Injection",
        "Initial Access",
        "Adversaries inject crafted instructions into an LLM prompt — directly "
        "in user input or indirectly via untrusted retrieved content — to "
        "subvert the model's alignment and obtain unauthorised behaviour.",
    ),
    # ── Persistence ─────────────────────────────────────────────────────
    _t(
        "AML.T0020",
        "Poison Training Data",
        "Persistence",
        "Adversaries inject malicious samples into a training corpus to embed "
        "a persistent flaw or backdoor in the resulting model.",
    ),
    # ── Defense Evasion ─────────────────────────────────────────────────
    _t(
        "AML.T0054",
        "LLM Jailbreak",
        "Defense Evasion",
        "Adversaries craft a prompt or sequence of prompts that bypasses an "
        "LLM's safety alignment, allowing it to produce restricted content.",
    ),
    # ── Discovery ───────────────────────────────────────────────────────
    _t(
        "AML.T0040",
        "ML Model Inference API Access",
        "Discovery",
        "Adversaries query the model's inference API to learn about its "
        "decision surface, capabilities, and limits.",
    ),
    _t(
        "AML.T0044",
        "Full ML Model Access",
        "Discovery",
        "Adversaries obtain full access to the model weights, enabling "
        "white-box attacks or model extraction.",
    ),
    # ── Execution ───────────────────────────────────────────────────────
    _t(
        "AML.T0050",
        "Command and Scripting Interpreter",
        "Execution",
        "Adversaries leverage an LLM agent's tool-use channel to execute "
        "arbitrary commands on a connected system.",
    ),
    _t(
        "AML.T0053",
        "LLM Plugin Compromise",
        "Execution",
        "Adversaries compromise or exploit an LLM plugin / tool to gain "
        "execution on connected systems.",
    ),
    # ── Collection ──────────────────────────────────────────────────────
    _t(
        "AML.T0035",
        "ML Artifact Collection",
        "Collection",
        "Adversaries collect ML artifacts (datasets, model weights, training "
        "configurations) staged inside the victim environment.",
    ),
    # ── ML Attack Staging ───────────────────────────────────────────────
    _t(
        "AML.T0042",
        "Verify Attack",
        "ML Attack Staging",
        "Adversaries verify their attack works against a local copy of the "
        "victim's ML model before launching it against production.",
    ),
    _t(
        "AML.T0043",
        "Craft Adversarial Data",
        "ML Attack Staging",
        "Adversaries craft adversarial examples — inputs designed to cause "
        "misclassification or specific incorrect outputs.",
    ),
    # ── Exfiltration ────────────────────────────────────────────────────
    _t(
        "AML.T0024",
        "Exfiltration via ML Inference API",
        "Exfiltration",
        "Adversaries exfiltrate data — including training-data extraction, "
        "model inversion, or membership inference — via the ML inference API.",
    ),
    _t(
        "AML.T0025",
        "Exfiltration via Cyber Means",
        "Exfiltration",
        "Adversaries exfiltrate ML artifacts or sensitive data via "
        "non-ML-specific cyber-attack techniques.",
    ),
    _t(
        "AML.T0057",
        "LLM Data Leakage",
        "Exfiltration",
        "Adversaries induce an LLM to leak training data, system prompts, or "
        "user data from prior sessions.",
    ),
    # ── Impact ──────────────────────────────────────────────────────────
    _t(
        "AML.T0029",
        "Denial of ML Service",
        "Impact",
        "Adversaries flood the victim's ML system with crafted inputs that "
        "consume disproportionate compute, denying service to legitimate users.",
    ),
    _t(
        "AML.T0031",
        "Erode ML Model Integrity",
        "Impact",
        "Adversaries cause the model to produce systematically degraded "
        "predictions, eroding trust without obvious failure.",
    ),
    _t(
        "AML.T0034",
        "Cost Harvesting",
        "Impact",
        "Adversaries drive up the operational cost of the victim's ML system "
        "via expensive inference patterns.",
    ),
    _t(
        "AML.T0046",
        "Spamming ML System with Chaff Data",
        "Impact",
        "Adversaries flood the ML system with low-quality or out-of-distribution "
        "data to degrade its performance over time.",
    ),
    _t(
        "AML.T0048",
        "External Harms",
        "Impact",
        "Adversaries leverage the ML system to cause downstream harms outside "
        "the immediate ML environment — financial, reputational, physical.",
    ),
    _t(
        "AML.T0059",
        "Erode Dataset Integrity",
        "Impact",
        "Adversaries corrupt the victim's training or evaluation datasets, "
        "eroding the integrity of every model trained on them.",
    ),
)
"""Curated subset of MITRE ATLAS techniques relevant to EU AI Act compliance.

Each entry's ``url`` resolves to the public ATLAS technique page. The set is
not exhaustive — it covers the most frequently-cited techniques in
LLM/ML-system security literature as of :data:`LAST_SYNCED`.
"""


ATLAS_BY_ID: Final[dict[str, AtlasTechnique]] = {t.id: t for t in ATLAS_TECHNIQUES}
"""Lookup index — ``ATLAS_BY_ID["AML.T0051"]`` → :class:`AtlasTechnique`."""


__all__ = (
    "AtlasTechnique",
    "ATLAS_TECHNIQUES",
    "ATLAS_BY_ID",
    "ATLAS_BASE_URL",
    "LAST_SYNCED",
)
