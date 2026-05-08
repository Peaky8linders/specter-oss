# /specter:role-obligations

Return the EU AI Act articles that apply to a given operator role.

## Operator roles

| Role slug | Definition |
|---|---|
| `provider` | Places a high-risk system on the market under their own name |
| `deployer` | Uses a high-risk system in the course of activities |
| `importer` | Brings a non-EU-built system into the EU market |
| `distributor` | Makes a system available in the supply chain |
| `product_manufacturer` | Embeds an AI system into a regulated product (Art. 25) |
| `authorized_representative` | Non-EU provider's EU-resident agent (Art. 22) |
| `gpai_provider` | General-Purpose AI Model provider (Art. 53) |
| `gpai_systemic_provider` | GPAI provider with systemic-risk model (Art. 55) |
| `extraterritorial_non_eu` | Non-EU operator with EU-market AI output (Art. 2(1)(c)) |

## Usage

```
/specter:role-obligations role="deployer"
/specter:role-obligations role="gpai_systemic_provider"
```

## Returns

```json
{
  "found": true,
  "role": "deployer",
  "label": "Deployer",
  "definition": "A natural or legal person ... using an AI system under its authority ...",
  "article_count_primary": 4,
  "article_count_secondary": 11,
  "primary_articles": ["Art. 26", "Art. 27", "Art. 29", "Art. 50"],
  "secondary_articles": ["Art. 4", "Art. 13", "Art. 14", ...]
}
```

When the role slug is unknown, returns `{found: false, valid_roles: [...]}`.

## When to use

- Drafting a compliance roadmap scoped to a specific operator role
- Filtering a portfolio's obligation list by what applies to the
  customer's actual role
- Resolving "who's responsible" when a finding spans the value
  chain (cross-reference with the `attribution` axis from
  `/specter:taxonomy`)

Wraps `specter.data.roles.articles_for_role` + `get_role_obligation`
via the `specter_role_obligations` MCP tool.
