# /specter:check-article

Validate an EU AI Act article reference against the canonical
113-article + 13-annex catalog from Regulation (EU) 2024/1689.

The catalog applies prefix-fallback semantics: a citation like
`Art. 13(1)(a)` is valid if `Art. 13` exists. Same for
`Annex IV(2)` against `Annex IV`. References to articles outside
the regulation (e.g. `Art. 999`) return invalid.

## Usage

```
/specter:check-article ref="Art. 13(1)(a)"
/specter:check-article ref="Annex IV(2)"
/specter:check-article ref="Art. 999"
```

## Returns

```json
{
  "valid": true,
  "resolved": "Art. 13",
  "exact_match": false,
  "note": "matched via prefix-fallback (sub-paragraph inheritance)"
}
```

When invalid:

```json
{
  "valid": false,
  "reason": "reference does not exist in the EU AI Act catalog"
}
```

## When to use

- Before drafting a citation in a compliance document or audit report
- As a hallucination guard inside an LLM Q&A pipeline
- To validate user-supplied references in a compliance dashboard

Wraps `specter.data.articles_existence.ARTICLE_EXISTENCE` via the
`specter_check_article` MCP tool.
