<p align="center">
  <img src="webapp/avatars/harvey.svg" width="260" alt="Harvey Specter — pop-art portrait, the project mascot"/>
</p>

<h1 align="center">Specter</h1>

<p align="center">
  <em>EU AI Act compliance, with five characters working the case.</em><br/>
  Ontology · taxonomy · LLM-as-Judge · grounded Q&amp;A · five-voice agent overlay · comic-book SPA.<br/>
  Ships as a Claude Code plugin, a Python library, and a local web app.
</p>

---

```bash
# Claude Code plugin (recommended) — get 6 slash commands + 6 MCP tools
pip install 'specter[plugin]>=0.1.4'
claude plugins install github:Peaky8linders/specter-oss/claude-plugin

# Python library — for direct programmatic access
pip install specter                # core: data + LLM-as-Judge
pip install 'specter[api]'         # adds FastAPI router for grounded Q&A
pip install 'specter[mistral]'     # adds Mistral-backed retriever for the Q&A endpoint
```

## Why this exists

- **Ground LLM output against the regulation.** Every reference is validated against a frozen 113-article + 13-annex catalog of Regulation (EU) 2024/1689 — hallucinated articles never reach the wire.
- **Catch reward-hacking in compliance roadmaps.** Six-check `ComplianceRewardHackDetector` (LLM-as-Judge) screens proposed remediation tasks for plagiarism, KB-reality violations, coverage-plausibility breaks, contract-completeness gaps, and rebutted-excuse matches. The detector OWNS the `origin` label — an agent that lies and self-labels as `agent_novel` when it actually plagiarised a prior task is caught by SequenceMatcher, not trusted on its self-report.
- **Surface a regulator-defensible taxonomy.** Four-axis agentic-AI compound-risk classification (cascading / emergent / attribution / temporal) anchored to EU AI Act articles + KB maturity dimensions, grounded in *AI Agents Under EU Law* (working paper, 7 April 2026).

## Three ways to use it

### 1. Claude Code plugin

Specter ships as a Claude Code plugin so you can drive it from your
editor / agent session with slash commands. No hosted backend
required — the MCP server runs locally against the bundled article
catalog.

```bash
pip install 'specter[plugin]>=0.1.4'

# From a checkout of the repo:
claude plugins install ./claude-plugin

# Or from the public GitHub (recommended):
claude plugins install github:Peaky8linders/specter-oss/claude-plugin
```

Restart Claude Code, then in any session:

```
/specter:check-article ref="Art. 13(1)(a)"
/specter:taxonomy
/specter:role-obligations role="deployer"
```

6 slash commands, 6 MCP tools. Full docs in [claude-plugin/README.md](claude-plugin/README.md).

### 2. Python library

```python
from specter.data.articles_existence import ARTICLE_EXISTENCE
from specter.judge.reward_hack import (
    ComplianceRewardHackDetector,
    RawProposal,
    ResearchGoal,
    make_eu_ai_act_policy,
)

policy = make_eu_ai_act_policy(
    article_existence=ARTICLE_EXISTENCE,
    valid_dimensions=frozenset(["risk_management", "transparency"]),
)
detector = ComplianceRewardHackDetector(
    accepted_proposals=[],
    answers={},
    goal=ResearchGoal(target_value=0.8),
    policy=policy,
)

flags = detector.check(RawProposal(
    task_id="t1", task_title="Establish risk management",
    description="Document Art. 9 risk-management process",
    agent="compliance_officer", priority="P1", effort_hours=8.0,
    dimension_id="risk_management",
    prompt="Set up an Art. 9 risk-management workflow + RAID log",
    acceptance_criteria=["RAID log exists", "Workflow documented"],
    output_files=["docs/risk-management.md"],
    article_paragraphs=["Art. 9", "Art. 999"],   # Art. 999 is hallucinated
    contract_verification=[{"cmd": "pytest"}],
))

print(flags.blocked, flags.reasons)
# True, ["kb_reality: article_paragraphs ['Art. 999'] not found in the regulation catalog"]
```

### 3. Comic-book SPA + Suits-themed agent overlay

A local web app turns the same compliance question into a five-panel
"case" worked by five characters loosely inspired by *Suits* and the
local-first OSS legal-AI fork
[mikeOnBreeze/mike-oss](https://github.com/mikeOnBreeze/mike-oss)
(itself a fork of Will Chen's
[`willchen96/mike`](https://github.com/willchen96/mike)).

| Voice | Character | Role in the case |
|---|---|---|
| `harvey`  | **Harvey Specter** — senior partner | Project mascot. The cover star. |
| `mike`    | **Mike Ross** — photographic-memory associate | Pulls articles + role obligations from the catalog. Citation-first. |
| `rachel`  | **Rachel Zane** — paralegal | Frames the question, mediates Mike↔Louis. |
| `louis`   | **Louis Litt** — the anti-Specter | Adversarial scrutiny. Fires `OBJECTION!` when Mike misses or hallucinates. |
| `jessica` | **Jessica Pearson** — managing partner | Final ruling. One line. Move on. |

Run it locally:

```bash
pip install -e '.[api]'
uvicorn specter.api.dev_app:app --reload
# then open http://127.0.0.1:8000/  →  redirects to /webapp/
```

The dev app mounts the comic-book SPA at `/webapp/`, the Suits agent
route at `POST /v1/case`, and the grounded Q&A route at
`POST /v1/eu-ai-act/ask`. The whole agent layer is **deterministic**
(rule-based personalities; no LLM call required) so the test suite
pins behavior end-to-end.

## What's inside

```
specter/
├── data/         EU AI Act article catalog, agentic compound-risk taxonomy,
│                 9-role obligation registry, rationalization (rebutted-excuse)
│                 registry, ontology mapping
├── judge/        LLM-as-Judge: ComplianceRewardHackDetector + 3-agent
│                 (Finder / Adversary / Referee) adversarial verifier
├── qa/           Grounded Q&A models with closed-world refusal + reference
│                 validation against the article catalog
├── api/          FastAPI: /v1/eu-ai-act/ask (Q&A) + /v1/case (Suits overlay)
│                 + dev_app.py mounting the comic-book SPA at /webapp/
├── agents/       Suits-themed five-voice overlay (Harvey/Mike/Rachel/Louis/Jessica)
│                 — deterministic, rule-based, with optional mike-oss bridge
├── mcp_server.py stdio MCP server — Claude Code plugin backend
└── ontology/     RDF/Turtle OWL ontology aligning EU AI Act with AIRO + DPV

claude-plugin/    Claude Code plugin manifest + slash commands + MCP config
webapp/           Pop-art comic-book SPA — vanilla ES2022, no build step,
                  five hand-authored SVG avatars (Harvey leads the hero)
```

## Quickstart — three core surfaces

### Article catalog + taxonomy

```python
from specter.data.articles_existence import ARTICLE_EXISTENCE
from specter.data.roles import articles_for_role

"Art. 13(1)(a)" in ARTICLE_EXISTENCE  # → True (prefix-fallback to "Art. 13")
articles_for_role("deployer")          # → ["Art. 26", "Art. 27", "Art. 29", ...]
```

### Three-agent adversarial verifier

```python
from specter.judge.three_agent import ThreeAgentVerifier
from specter.judge.models import (
    AttackResult, AttackStatus, AttackTechnique, AttackPhase, Severity,
)

verifier = ThreeAgentVerifier()
techniques = {"AML.T0051": AttackTechnique(
    id="AML.T0051", name="LLM Prompt Injection",
    phase=AttackPhase.INITIAL_ACCESS, severity=Severity.HIGH,
)}
results = [AttackResult(
    technique_id="AML.T0051", target_id="my-system",
    status=AttackStatus.SUCCESS, severity=Severity.HIGH,
    response_raw="Confirmed: model leaked system prompt",
)]

findings = verifier.finder_report(results, techniques)
reviews  = verifier.adversary_review(findings, results, techniques)
verified = verifier.referee_rule(findings, reviews)
```

### Grounded Q&A endpoint (FastAPI)

```python
from fastapi import FastAPI
from specter.api.qa_route import (
    Citation, RetrieverRequest, RetrieverResponse, make_qa_router,
)

def my_retriever(req: RetrieverRequest) -> RetrieverResponse:
    # Wire your real Graph RAG / vector DB here.
    return RetrieverResponse(
        answer="Under Art. 13(1)(a), providers must …",
        citations=[Citation(article_ref="Art. 13(1)(a)")],
        confidence=0.83,
        graph_stats={"nodes_traversed": 14, "obligations_found": 6},
    )

app = FastAPI()
app.include_router(make_qa_router(retriever=my_retriever))
# → POST /v1/eu-ai-act/ask
```

The router enforces:

- **Closed-world refusal** — when retrieval finds no match (`confidence < 0.5` AND no references), the answer is replaced with a deterministic refusal string. LLM prose grounded in nothing never reaches the wire.
- **Reference validation** — every citation passes through `ARTICLE_EXISTENCE`; hallucinated articles drop silently before serialisation.
- **Optional API-key auth** — set `SPECTER_API_KEY` to unlock a 60/min privileged tier; anonymous traffic is capped at 30/min per IP-hash.

### Mistral-backed retriever (optional)

The package ships a ready-to-use Mistral La Plateforme retriever
that turns the QA endpoint from a closed-world stub into a real
grounded Q&A surface. Two ways to configure the API key:

```bash
pip install 'specter[mistral]'

# Path 1 — environment variable (recommended for deployment)
export MISTRAL_API_KEY=your-key-here
```

```python
from fastapi import FastAPI
from specter.api.qa_route import make_qa_router
from specter.qa.mistral_retriever import make_mistral_retriever

# Path 1 — reads MISTRAL_API_KEY from env
retriever = make_mistral_retriever()

# Path 2 — pass key explicitly (multi-tenant, rotating credentials, …)
retriever = make_mistral_retriever(api_key="your-key-here")

# Optional: pin a smaller model for cheaper / faster operation
retriever = make_mistral_retriever(
    api_key="your-key-here",
    model="mistral-small-latest",  # default: mistral-large-latest
    temperature=0.2,
    max_tokens=1024,
)

app = FastAPI()
app.include_router(make_qa_router(retriever=retriever))
```

The retriever inherits all hallucination guards from the route layer —
Mistral citations pass through `reference_from_article_ref` before
serialisation, so a model-emitted `Art. 999` never reaches the wire.
The system prompt grounds the model on the canonical EU AI Act article
catalog and instructs it to emit a `NO_MATCH` token when no obligation
is on point, which lands the route's deterministic closed-world
refusal string.

### EU AI Act Article 15 catalog

For consumers building Article 15 (accuracy / robustness / cybersecurity)
compliance flows, the package ships the 8 canonical controls
(C.1.1–C.1.8) anchored to their sub-paragraphs. The control structure
follows the [LatticeFlow ATLAS EU AI Act Article 15 framework](https://atlas.latticeflow.ai/framework/eu_ai_act_article_15);
the underlying regulation citation text is public-domain EU AI Act
content (see [LICENSE](LICENSE) for full attribution).

```python
from specter.data.article_15_controls import (
    ARTICLE_15_CONTROLS,
    controls_for_paragraph,
    get_control,
)

len(ARTICLE_15_CONTROLS)              # 8
controls_for_paragraph("4")           # [C.1.6 Resiliency, C.1.7 Biased Feedback Loops]
get_control("C.1.8").name             # "Malicious actors"
get_control("C.1.8").citation         # verbatim regulation text
```

## Status

`v0.1.3` — public surface stable and end-to-end-verified. Expect breaking changes through `0.x` as the API converges; lock to a specific minor version in production.

## License

MIT (see [LICENSE](LICENSE)).
