# /specter:taxonomy

Return the four-axis **agentic-AI compound-risk taxonomy** grounded
in *AI Agents Under EU Law* (Working Paper, 7 April 2026), §10.4.

## The four axes

| Axis | Definition | Article anchors | KB dimensions |
|---|---|---|---|
| **cascading** | Error/bias propagates across orchestrated sub-agents | Art. 9, 10, 15, 25(4) | risk_mgmt, data_gov, security, decision_governance |
| **emergent** | Unsafe collective behaviour from individually safe agents | Art. 9, 14, 15(4), 51(2), 55 | risk_mgmt, human_oversight, security, gpai_systemic_risk |
| **attribution** | Multi-provider value chain obscures responsibility | Art. 3(23), 25, 25(4), 74, 53 | supply_chain, quality_management, tech_docs, deployer_obligations |
| **temporal** | Long-running state drift outside conformity envelope | Art. 3(23), 12, 14, 15, 43, 72, 73 | logging, human_oversight, security, conformity_assessment |

## Why this exists

The paper observes that **no current EU instrument provides a risk
taxonomy for compound AI systems** — Recital 116 only mandates one
for GPAI systemic risk; ISO/IEC 42005 + 23894 manage organisational
risk to the organisation, not Article 9's external-rights scope.
Specter ships the canonical reference implementation so any
downstream consumer can ground their threat model in a regulator-
defensible classification.

## Usage

```
/specter:taxonomy
```

## Returns

```json
{
  "version": "2026.04.27.v1",
  "compound_risk_types": ["cascading", "emergent", "attribution", "temporal"],
  "compound_risks": [...],
  "threat_categories": [...],
  "agent_archetypes": [...]
}
```

Each `compound_risks[*]` entry carries:

- `id` + `label` + `summary`
- `paper_section` + `paper_lines` (citation back to source)
- `article_refs` — anchored EU AI Act articles
- `kb_dimensions` — KB rows the axis maps onto
- `failure_modes` — concrete examples drawn from cited literature
- `mitigation_pattern` — engineering responses
- `evidence_required` — audit artefacts an external assessor expects
- `threat_categories` — Kim et al. / Hammond et al. / OWASP / AEPD
  cross-walks

## When to use

- Building a threat model for a compound AI system
- Fact-checking an LLM-generated risk-mgmt narrative against a
  regulator-grounded taxonomy
- Mapping a security finding to one of the four axes for an
  Annex IV technical-doc package

Wraps `specter.data.taxonomy` via the `specter_get_taxonomy` MCP tool.
