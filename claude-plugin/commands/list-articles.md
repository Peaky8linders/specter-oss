# /specter:list-articles

Return the canonical EU AI Act surface — 113 articles + 13 annexes
from Regulation (EU) 2024/1689.

## Usage

```
/specter:list-articles                  # all (default)
/specter:list-articles kind="articles"  # 113 articles only
/specter:list-articles kind="annexes"   # 13 annexes only
```

## Returns

```json
{
  "articles": { "count": 113, "items": ["Art. 1", "Art. 2", ...] },
  "annexes":  { "count": 13,  "items": ["Annex I", "Annex II", ...] },
  "total": 126
}
```

## When to use

- Grounding an LLM's free-text generation against an authoritative
  list before it cites
- Building a dropdown / picker UI for a compliance assessment form
- Auditing an internal article catalog against the regulation surface

Wraps `specter.data.articles_existence.ARTICLE_EXISTENCE` via the
`specter_list_articles` MCP tool.
