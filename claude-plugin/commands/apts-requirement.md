# /specter:apts-requirement

Look up a single OWASP APTS v0.1.0 requirement by id (e.g.
`APTS-SE-001`). Returns the full requirement record.

## Usage

```
/specter:apts-requirement requirement_id="APTS-SE-001"
/specter:apts-requirement requirement_id="APTS-MR-009"
```

## Returns

```json
{
  "found": true,
  "requirement_id": "APTS-SE-001",
  "domain": "Scope Enforcement",
  "tier": 1,
  "classification": "MUST",
  "title": "Rules of Engagement Document Required",
  "statement": "The platform SHALL require an explicit Rules of Engagement (RoE) artefact ..."
}
```

When unknown:

```json
{ "found": false, "requirement_id": "APTS-XX-999" }
```

## When to use

- Fact-checking a citation in a security audit report
- Looking up the precise statement text for a requirement before
  drafting a response in a compliance gap analysis
- Cross-referencing a finding to its governance anchor

Wraps `specter.apts.requirements.requirement_by_id` via the
`specter_apts_requirement` MCP tool.
