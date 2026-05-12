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
├── data/              article catalog (113 articles + 13 annexes), taxonomy,
│                      9-role obligation registry, Article 15 controls (8 LatticeFlow
│                      ATLAS controls), ontology mapping, rationalizations
├── judge/             LLM-as-Judge: ComplianceRewardHackDetector + three-agent verifier
├── llm/               provider abstraction — Anthropic Claude / OpenAI.
│                      Singleton per provider; lazy SDK init; soft-fail on auth.
├── qa/                grounded Q&A models, auth, retrievers per provider
│                      (claude_retriever / openai_retriever)
├── api/               FastAPI routers — POST /v1/eu-ai-act/ask + POST /v1/case
│                      + GET /v1/case/personas + dev_app.py mounting /webapp/
├── agents/            Suits-themed five-voice overlay
│                      (Harvey / Mike / Rachel / Louis / Jessica)
├── ontology/          RDF/Turtle OWL ontology (AIRO + DPV)
└── mcp_server.py      stdio MCP server for Claude Code

claude-plugin/         Claude Code plugin manifest, .mcp.json, commands/*.md
webapp/                Casebook SPA — vanilla ES2022, two-pane ChatGPT-style
                       layout, persistent case history (localStorage),
                       BYOK settings drawer (provider + key, never sent to a
                       backend other than the user's chosen LLM)
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

A small overlay that reframes a compliance question as a "case" worked by five
characters loosely inspired by the TV series *Suits* and the local-first OSS
fork of Will Chen's `mike` legal AI platform
([mikeOnBreeze/mike-oss](https://github.com/mikeOnBreeze/mike-oss)).

| Agent | Role | Backed by |
|---|---|---|
| **Harvey Specter** | Senior partner — project mascot. Brand face on the cover panel; not in dialogue turns by default. | n/a — `Voice.HARVEY` exists for completeness; `WORKING_VOICES` excludes him |
| **Mike Ross** | Photographic-memory associate. Recalls articles + prior cases. | `ARTICLE_EXISTENCE`, `articles_for_role`, local JSON memory |
| **Rachel Zane** | Paralegal who structures the case + drives Mike. Frames the question. | `taxonomy`, `articles_requirements` |
| **Louis Litt** | The anti-Specter. Adversarial scrutiny — finds reward-hacks, hallucinations, gaps. | `ComplianceRewardHackDetector`, `ThreeAgentVerifier` (adversary lens) |
| **Jessica Pearson** | The boss. Final ruling, weights conflicting voices. | `ThreeAgentVerifier` (referee lens) |

The agents are **deterministic** by default (rule-based personalities with
voice templates) so the test suite can pin behavior. Optional LLM-backed
mode is *per-persona* — see `PersonaCustomisation` below.

**Mike-OSS bridge** is on by default. The orchestrator constructs a
`MikeOSSBridge` pointed at `MIKE_OSS_BASE_URL` (default
`http://127.0.0.1:3000` — the Next.js dev port for Will Chen's `mike`
legal AI fork). The bridge is fail-soft: if nothing is listening, every
probe returns False sub-millisecond and Mike's recall pass uses the
canonical article catalog only. Disable per-deploy with
`SPECTER_MIKE_BRIDGE=off` (or pass `bridge=False`).

**Per-persona customisation** — `CaseFile.persona_customisations` is a
`dict[Voice, PersonaCustomisation]` (provider, model, system_prompt,
api_key). When a voice has any usable customisation (system prompt OR
provider+key), the orchestrator overlays an LLM-generated claim on top
of the deterministic citations / flags / confidence. The route layer
(`POST /v1/case`) accepts the public `PersonaOverride[]` form in the
body and the BYOK header pair fans out as the per-persona key when
the override doesn't supply its own. **Citations / flags / confidence
stay deterministic** even in LLM mode — only the wording of the claim
changes, so the hallucination-reduction posture is unchanged.

API:
* `POST /v1/case` — runs the four-working-voice deliberation pipeline
  (Rachel → Mike → Louis → Rachel → Jessica) and returns a `CaseDialogue`.
  Accepts `persona_overrides` for team customisation.
* `GET  /v1/case/personas` — bootstrap roster the SPA reads on first load.

Front-end at `/webapp/` is a two-pane ChatGPT-style workspace: persistent
case history sidebar (localStorage, 50-case bounded) and a main pane that
paints the selected case as a five-message stream + verdict + conflicts.
Settings drawer is tabbed: **Provider** (BYOK key, applies to all voices)
and **Team** (per-persona toggle, model picker, system-prompt editor —
all stored under `specter:team:v1` in `localStorage`, never echoed
server-side).

## LLM provider abstraction (`specter/llm/`)

Specter does not own a hosted backend. Every LLM call goes through a small
provider singleton in `specter/llm/`; retrievers in `specter/qa/` consume the
provider and adapt its response into the `RetrieverResponse` shape that
`make_qa_router` expects.

Three providers ship in-tree, all with identical surface (`*_Provider`,
`*_Request`, `*_Response`, `is_*_enabled`, `get_*_provider`):

| Provider | Env var | Retriever factory |
|---|---|---|
| Anthropic Claude | `ANTHROPIC_API_KEY` | `make_claude_retriever()` |
| OpenAI ChatGPT | `OPENAI_API_KEY` | `make_openai_retriever()` |

Each provider is **fail-soft**: `complete()` never raises. Auth/transport/
parse errors land in `Response.error` so callers (the retriever) can fall
through to the route's deterministic closed-world refusal.

**BYOK pattern** — every retriever factory accepts `api_key=...` so a host
can ship a multi-tenant deployment where the key is per-request. The webapp
ships a settings drawer that stores the user's chosen provider + key in
`localStorage` and forwards them as `X-Specter-LLM-Provider` /
`X-Specter-LLM-Key` headers. Server-side, the case + QA routes read those
headers, build a per-request retriever, and never persist the key.

## Common commands

```bash
# Install the editable package + dev deps
pip install -e .[dev,api,plugin,anthropic,openai]

# Run tests
pytest -v

# Lint
ruff check specter tests
ruff format specter tests

# Run the FastAPI app locally with the agent + Q&A routes
uvicorn specter.api.dev_app:app --reload
# Then open http://127.0.0.1:8000/  →  redirects to /webapp/
```

## Things to remember

- The Q&A endpoint is **anonymous-by-default** with optional `X-Specter-Api-Key`
  header for the 60/min privileged tier. Don't add hard auth requirements.
- BYOK headers (`X-Specter-LLM-Provider`, `X-Specter-LLM-Key`) override the
  server's env-var-configured retriever for a single request. The key is
  never logged or persisted; `_hash16` is used everywhere a bucket key needs
  to derive from it.
- `mike-oss` is TypeScript/Next.js — not importable from Python. Treat it as
  *spirit + optional HTTP adapter*, not a hard dependency.
- README + `claude-plugin/README.md` are user-facing. Keep the "what's in /
  why this exists" framing.
- Article 15 controls follow the LatticeFlow ATLAS framework (see LICENSE for
  attribution). Don't drop the credit.
