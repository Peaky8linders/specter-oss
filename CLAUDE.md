# CLAUDE.md — specter-oss

> Project-local guidance for Claude Code. Cross-project rules live in `~/.claude/CLAUDE.md`.

## What this project is

**Specter** is an EU AI Act compliance toolkit (`pip install specter`) that ships
two surfaces:

1. **Python library** — `specter` package: data-pure article/role/taxonomy
   catalogs, LLM-as-Judge reward-hack detector, three-agent adversarial verifier,
   FastAPI Q&A router with closed-world refusal + reference validation.
2. **Claude Code plugin** — local stdio MCP server + 6 slash commands wrapping
   the same library (`claude-plugin/`).

Frozen knowledge base: **113 articles + 13 annexes** of Regulation (EU) 2024/1689,
plus the 8-control LatticeFlow ATLAS catalog for Article 15.

## Layout

```
specter/
├── data/              article catalog, taxonomy, roles, ontology, rationalizations
├── judge/             LLM-as-Judge: ComplianceRewardHackDetector + three-agent verifier
├── qa/                grounded Q&A models, auth, optional Mistral retriever
├── api/               FastAPI router (POST /v1/eu-ai-act/ask)
├── agents/            Suits-themed multi-agent overlay (Mike/Rachel/Louis/Jessica)
├── ontology/          RDF/Turtle OWL ontology (AIRO + DPV)
└── mcp_server.py      stdio MCP server for Claude Code

claude-plugin/         Claude Code plugin manifest, .mcp.json, commands/*.md
webapp/                Comic-book SPA front-end for the agent layer (static)
tests/                 pytest smoke tests pinning the public surface
```

## Hard rules (do not break)

- **Data-pure layers stay pure.** `specter/data/*` and `specter/qa/models.py`
  must remain deterministic for the same inputs — no I/O, no global mutable
  state. New side-effecting code goes in `specter/api/*`, `specter/agents/*`,
  or behind a small adapter.
- **Hallucinated articles never reach the wire.** Every external-facing
  reference passes through `reference_from_article_ref` which validates against
  `ARTICLE_EXISTENCE` and returns `None` on hallucination. Don't bypass it.
- **Closed-world refusal lives in the route layer.** The Q&A router replaces
  empty/low-confidence retriever output with a deterministic refusal string.
  Don't paper over it with cosmetic prose.
- **Public surface is locked at v0.1.x.** Additions OK; breaking changes need
  a version bump + CHANGELOG entry.

## Conventions

- Python ≥ 3.11. Type hints everywhere. Pydantic v2. `from __future__ import annotations`.
- Ruff line length 100, ruleset `E F I B UP` (see `pyproject.toml`).
- Tests: `pytest -v` (smoke tests in `tests/test_smoke.py`). New behaviour
  needs a smoke test pinning its contract.
- Comments explain the *why*, not the *what*. The existing codebase has long,
  carefully-worded section headers — match that voice when extending.

## Suits-themed agent layer (`specter/agents/`)

A small overlay that reframes a compliance question as a "case" worked by four
characters loosely inspired by the TV series *Suits* and the local-first OSS
fork of Will Chen's `mike` legal AI platform
([mikeOnBreeze/mike-oss](https://github.com/mikeOnBreeze/mike-oss)).

| Agent | Role | Backed by |
|---|---|---|
| **Mike Ross** | Photographic-memory associate. Recalls articles + prior cases. | `ARTICLE_EXISTENCE`, `articles_for_role`, local JSON memory |
| **Rachel Zane** | Paralegal who structures the case + drives Mike. Frames the question. | `taxonomy`, `articles_requirements` |
| **Louis Litt** | The anti-Specter. Adversarial scrutiny — finds reward-hacks, hallucinations, gaps. | `ComplianceRewardHackDetector`, `ThreeAgentVerifier` (adversary lens) |
| **Jessica Pearson** | The boss. Final ruling, weights conflicting voices. | `ThreeAgentVerifier` (referee lens) |

The agents are **deterministic** by default (rule-based personalities with
voice templates) so the test suite can pin behavior. Optional LLM-backed mode
calls Mistral via `make_mistral_retriever`.

API: `POST /v1/case` returns a `CaseDialogue` (ordered turns, each with
`speaker`, `voice`, `claim`, `citations`, `confidence`). Front-end at
`/webapp/` renders this as a comic book.

## Common commands

```bash
# Install the editable package + dev deps
pip install -e .[dev,api,plugin,mistral]

# Run tests
pytest -v

# Lint
ruff check specter tests
ruff format specter tests

# Run the FastAPI app locally with the agent + Q&A routes
uvicorn specter.api.dev_app:app --reload  # if dev_app exists
```

## Things to remember

- The Q&A endpoint is **anonymous-by-default** with optional `X-Specter-Api-Key`
  header for the 60/min privileged tier. Don't add hard auth requirements.
- `mike-oss` is TypeScript/Next.js — not importable from Python. Treat it as
  *spirit + optional HTTP adapter*, not a hard dependency.
- README + `claude-plugin/README.md` are user-facing. Keep the "what's in /
  why this exists" framing.
- Article 15 controls follow the LatticeFlow ATLAS framework (see LICENSE for
  attribution). Don't drop the credit.
