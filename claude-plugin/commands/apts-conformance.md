# /specter:apts-conformance

Return the OWASP APTS v0.1.0 self-conformance scorecard for the
reference platform — headline %, tier achievement (Foundation /
Verified / Comprehensive), per-domain breakdown across the 8
conformance domains.

OWASP APTS v0.1.0 is a governance standard for **autonomous
penetration testing** platforms. 173 requirements across 8 domains
(Scope Enforcement, Safety Controls, Human Oversight, Graduated
Autonomy, Auditability, Manipulation Resistance, Supply Chain Trust,
Reporting) split into three compliance tiers.

The shipped baseline lands at **~73.5% headline** with no tier
achieved yet. See [docs/evals/apts-self-conformance.md][1] for the
full markdown brief.

[1]: https://github.com/Peaky8linders/specter-oss/blob/main/docs/evals/apts-self-conformance.md

## Usage

```
/specter:apts-conformance
```

## Returns (abridged)

```json
{
  "apts_version": "0.1.0",
  "headline_score": 0.735,
  "headline_tier": null,
  "counts": { "total": 173, "satisfied": 95, "partial": 52, "gap": 26 },
  "tier_status": [
    { "tier": 1, "label": "Foundation",  "achieved": false, "must_satisfied": 52, "must_total": 72 },
    { "tier": 2, "label": "Verified",    "achieved": false, "must_satisfied": 88, "must_total": 141 },
    { "tier": 3, "label": "Comprehensive","achieved": false, "must_satisfied": 89, "must_total": 144 }
  ],
  "domain_summaries": [
    { "domain": "Manipulation Resistance", "satisfied": 18, "partial": 4, "gap": 1, "coverage_score": 0.900 },
    { "domain": "Auditability",            "satisfied": 15, "partial": 4, "gap": 1, "coverage_score": 0.846 },
    ...
  ]
}
```

## When to use

- Publishing your own APTS conformance baseline to a public page
- Periodic conformance regression check (run weekly, diff against
  the previous run)
- Fact-checking an LLM claim that the platform is "APTS Tier 2 ready"

Wraps `specter.apts.assess_self()` via the
`specter_apts_self_conformance` MCP tool.
