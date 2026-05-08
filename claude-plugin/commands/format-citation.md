# /specter:format-citation

Convert internal-form EU AI Act references (`Art. X(Y)(Z)`,
`Annex IV(N)`) into publication form (`Article X.Y.Z`, `Annex IV.N`).

Validates against the canonical catalog before formatting — a
hallucinated `Art. 999(z)` returns `null` instead of being
confidently reshaped into `Article 999.z` and shipped to
downstream consumers.

## Usage

```
/specter:format-citation ref="Art. 13(1)(a)"
/specter:format-citation ref="Annex IV(2)"
/specter:format-citation ref="Art. 999"
```

## Returns

```json
{ "input": "Art. 13(1)(a)", "formatted": "Article 13.1.a", "valid": true }
```

When invalid:

```json
{ "input": "Art. 999", "formatted": null, "valid": false }
```

## When to use

- Reformatting internal references for an external auditor's report
- Building a citation layer in an LLM-driven Q&A endpoint
- Migrating data between an internal `Art.` notation and the
  publication-style `Article` notation

Wraps `specter.qa.models.reference_from_article_ref` via the
`specter_format_citation` MCP tool.
