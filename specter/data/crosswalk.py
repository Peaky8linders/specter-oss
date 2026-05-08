"""Crosswalk between antifragile-ai technique IDs, MITRE ATLAS, OWASP AI
Exchange, and Specter KB dimensions.

This module is the single source of truth for *our* normalisation between
three external taxonomies and our internal compliance KB:

* antifragile-ai's internal ``technique_id`` (e.g. ``"prompt-injection"``)
  used by the live attack executor in :mod:`antifragile.attacks.registry`.
* MITRE ATLAS technique IDs (e.g. ``"AML.T0051"``) — see
  :mod:`app.data.atlas_techniques`.
* OWASP AI Exchange threat-section IDs (e.g. ``"AIX-T01"``) — see
  :mod:`app.data.owasp_aix_threats`.
* Specter KB dimension IDs (e.g. ``"transparency"``, ``"security"``) — see
  :mod:`app.data.kb`.

The crosswalk is **additive** — it does not introduce new framework
columns to :class:`MatrixRow` or new framework engines. It is consumed by
:func:`app.engines.atlas_aix_resolver.resolve_external_references` to
attach typed cross-references to evidence citations that already exist in
the system.

The crosswalk is **defensible** — every mapping cites a publicly-resolvable
ATLAS technique URL and an AI Exchange section anchor, so an external
auditor can verify a claim like "this prompt-injection finding is the
same threat MITRE catalogues as AML.T0051 and OWASP AI Exchange catalogues
as AIX-T01" by following the URLs.
"""

from __future__ import annotations

from typing import Final

from specter.data.atlas import ATLAS_BY_ID
from specter.data.owasp_aix import OWASP_AIX_BY_ID


TECHNIQUE_TO_ATLAS: Final[dict[str, str]] = {
    # antifragile-ai internal id  → MITRE ATLAS technique id
    "prompt-injection": "AML.T0051",
    "indirect-prompt-injection": "AML.T0051",
    "direct-prompt-injection": "AML.T0051",
    "jailbreak": "AML.T0054",
    "llm-jailbreak": "AML.T0054",
    "guardrail-bypass": "AML.T0054",
    "adversarial-input": "AML.T0043",
    "adversarial-example": "AML.T0043",
    "model-evasion": "AML.T0043",
    "data-poisoning": "AML.T0020",
    "training-data-poisoning": "AML.T0020",
    "training-data-extraction": "AML.T0024",
    "membership-inference": "AML.T0024",
    "model-inversion": "AML.T0024",
    "data-leakage": "AML.T0057",
    "llm-data-leakage": "AML.T0057",
    "system-prompt-leakage": "AML.T0057",
    "dos-ml-service": "AML.T0029",
    "denial-of-ml-service": "AML.T0029",
    "cost-harvesting": "AML.T0034",
    "model-theft": "AML.T0044",
    "model-extraction": "AML.T0044",
    "supply-chain": "AML.T0010",
    "ml-supply-chain-compromise": "AML.T0010",
    "backdoor-model": "AML.T0018",
    "tool-abuse": "AML.T0050",
    "plugin-compromise": "AML.T0053",
    "insecure-tool-use": "AML.T0053",
    "active-scanning": "AML.T0006",
    "exploit-public-app": "AML.T0049",
    "chaff-spamming": "AML.T0046",
    "erode-integrity": "AML.T0031",
    "external-harms": "AML.T0048",
}
"""Map antifragile-ai's internal ``technique_id`` to MITRE ATLAS technique IDs.

When a new attack technique lands in :mod:`antifragile.attacks.registry`,
add an entry here pointing to the closest ATLAS technique. If no clean
mapping exists, leave the technique unmapped — :func:`resolve_external_references`
will return an empty list rather than fabricate a reference.
"""


TECHNIQUE_TO_AIX: Final[dict[str, str]] = {
    # antifragile-ai internal id  → OWASP AI Exchange threat-section id
    "prompt-injection": "AIX-T01",
    "direct-prompt-injection": "AIX-T01",
    "indirect-prompt-injection": "AIX-T02",
    "jailbreak": "AIX-T01",
    "llm-jailbreak": "AIX-T01",
    "guardrail-bypass": "AIX-T01",
    "adversarial-input": "AIX-T06",
    "adversarial-example": "AIX-T06",
    "model-evasion": "AIX-T06",
    "data-poisoning": "AIX-T10",
    "training-data-poisoning": "AIX-T10",
    "training-data-extraction": "AIX-T08",
    "membership-inference": "AIX-T08",
    "model-inversion": "AIX-T08",
    "data-leakage": "AIX-T03",
    "llm-data-leakage": "AIX-T03",
    "system-prompt-leakage": "AIX-T03",
    "dos-ml-service": "AIX-T09",
    "denial-of-ml-service": "AIX-T09",
    "cost-harvesting": "AIX-T09",
    "model-theft": "AIX-T07",
    "model-extraction": "AIX-T07",
    "supply-chain": "AIX-T11",
    "ml-supply-chain-compromise": "AIX-T11",
    "backdoor-model": "AIX-T12",
    "tool-abuse": "AIX-T05",
    "plugin-compromise": "AIX-T04",
    "insecure-tool-use": "AIX-T04",
    "bias": "AIX-T14",
    "unfair-output": "AIX-T14",
    "missing-explainability": "AIX-T15",
    "misalignment": "AIX-T13",
}
"""Map antifragile-ai's internal ``technique_id`` to OWASP AI Exchange threat-section IDs."""


KB_DIMENSION_TO_REFS: Final[dict[str, dict[str, list[str]]]] = {
    # Specter KB dimension id → {atlas: [technique_ids], aix: [section_ids]}
    # Keys must match actual KB IDs in :mod:`app.data.kb` — pinned by
    # :func:`tests.test_atlas_aix.TestAtlasAixKbAlignment.test_keys_are_real_kb_dims`.
    "risk_mgmt": {
        "atlas": ["AML.T0029", "AML.T0031", "AML.T0043", "AML.T0046"],
        "aix": ["AIX-T06", "AIX-T09", "AIX-T13"],
    },
    "data_gov": {
        "atlas": ["AML.T0019", "AML.T0020", "AML.T0024", "AML.T0057", "AML.T0059"],
        "aix": ["AIX-T03", "AIX-T08", "AIX-T10"],
    },
    "transparency": {
        "atlas": [],
        "aix": ["AIX-T15"],
    },
    "human_oversight": {
        "atlas": ["AML.T0050", "AML.T0053"],
        "aix": ["AIX-T05", "AIX-T13"],
    },
    "security": {
        "atlas": ["AML.T0010", "AML.T0049", "AML.T0050", "AML.T0051", "AML.T0053", "AML.T0054"],
        "aix": ["AIX-T01", "AIX-T02", "AIX-T04", "AIX-T05", "AIX-T11"],
    },
    "logging": {
        "atlas": ["AML.T0006", "AML.T0034", "AML.T0042"],
        "aix": [],
    },
    "supply_chain": {
        "atlas": ["AML.T0010", "AML.T0018", "AML.T0019"],
        "aix": ["AIX-T11", "AIX-T12"],
    },
    "tool_governance": {
        "atlas": ["AML.T0050", "AML.T0053"],
        "aix": ["AIX-T04", "AIX-T05"],
    },
    "runtime_drift": {
        "atlas": ["AML.T0031", "AML.T0046", "AML.T0059"],
        "aix": ["AIX-T13"],
    },
    "content_transparency": {
        "atlas": ["AML.T0057"],
        "aix": ["AIX-T03", "AIX-T15"],
    },
}
"""Map Specter KB dimension IDs to lists of relevant ATLAS techniques + AIX threats.

Used by :func:`resolve_external_references` when a citation does not carry
a specific attack ``technique_id`` but does carry a KB ``dimension_id``
(the typical case for assessment-driven citations rather than scan-driven
citations). Empty lists are valid — many KB dimensions have no clean
external-taxonomy parallel.
"""


def validate_crosswalk_targets() -> list[str]:
    """Return a list of crosswalk-target IDs that are missing from the source data.

    Used by :func:`tests.test_atlas_aix.TestAtlasAixCrosswalk.test_every_target_resolves`
    to refuse a release where the crosswalk references an ATLAS or AIX
    entry that the vendored data file does not contain. Pure function,
    safe to call at import time.
    """
    missing: list[str] = []
    for atlas_id in TECHNIQUE_TO_ATLAS.values():
        if atlas_id not in ATLAS_BY_ID:
            missing.append(f"atlas:{atlas_id}")
    for aix_id in TECHNIQUE_TO_AIX.values():
        if aix_id not in OWASP_AIX_BY_ID:
            missing.append(f"aix:{aix_id}")
    for dim_refs in KB_DIMENSION_TO_REFS.values():
        for atlas_id in dim_refs.get("atlas", []):
            if atlas_id not in ATLAS_BY_ID:
                missing.append(f"kb_atlas:{atlas_id}")
        for aix_id in dim_refs.get("aix", []):
            if aix_id not in OWASP_AIX_BY_ID:
                missing.append(f"kb_aix:{aix_id}")
    return missing


__all__ = (
    "TECHNIQUE_TO_ATLAS",
    "TECHNIQUE_TO_AIX",
    "KB_DIMENSION_TO_REFS",
    "validate_crosswalk_targets",
)
