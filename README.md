# Specter

> EU AI Act compliance toolkit — ontology, taxonomy, LLM-as-Judge, OWASP APTS conformance, grounded Q&A. Ships as a Python library and a Claude Code plugin.

```bash
pip install specter                # core: data + LLM-as-Judge + APTS conformance
pip install 'specter[api]'         # adds FastAPI router for grounded Q&A
pip install 'specter[plugin]'      # adds MCP SDK for the Claude Code plugin
```

## Why this exists

- **Ground LLM output against the regulation.** Every reference is validated against a frozen 113-article + 13-annex catalog of Regulation (EU) 2024/1689 — hallucinated articles never reach the wire.
- **Catch reward-hacking in compliance roadmaps.** Six-check `ComplianceRewardHackDetector` (LLM-as-Judge) screens proposed remediation tasks for plagiarism, KB-reality violations, coverage-plausibility breaks, contract-completeness gaps, and rebutted-excuse matches. The detector OWNS the `origin` label — an agent that lies and self-labels as `agent_novel` when it actually plagiarised a prior task is caught by SequenceMatcher, not trusted on its self-report.
- **Re-derive a public OWASP APTS scorecard.** Frozen 73.5% headline self-conformance baseline, 173 requirements × 8 domains × 3 tiers, deterministic given the same evidence map.

## Two ways to use it

### 1. Python library

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

### 2. Claude Code plugin

The same surface is shipped as a Claude Code plugin. Install once,
then use slash commands directly in your Claude Code session:

```bash
pip install 'specter[plugin]>=0.1.1'

# From a checkout of the repo:
claude plugins install ./claude-plugin

# Or from the public GitHub:
claude plugins install github:Peaky8linders/specter-oss/claude-plugin
```

Restart Claude Code, then in any session:

```
/specter:check-article ref="Art. 13(1)(a)"
/specter:apts-conformance
/specter:taxonomy
```

8 slash commands, 8 MCP tools. Full docs in [claude-plugin/README.md](claude-plugin/README.md).

## What's inside

```
specter/
├── data/         EU AI Act article catalog, agentic compound-risk taxonomy,
│                 9-role obligation registry, MITRE ATLAS + OWASP AI Exchange
│                 crosswalks, rationalization (rebutted-excuse) registry
├── judge/        LLM-as-Judge: ComplianceRewardHackDetector + 3-agent
│                 (Finder / Adversary / Referee) adversarial verifier
├── qa/           Grounded Q&A models with closed-world refusal + reference
│                 validation against the article catalog
├── api/          FastAPI router exposing POST /v1/eu-ai-act/ask with
│                 pluggable retriever
├── apts/         OWASP APTS (Autonomous Penetration Testing Standard)
│                 v0.1.0 conformance engine + curated evidence map
├── mcp_server.py stdio MCP server — Claude Code plugin backend
└── ontology/     RDF/Turtle OWL ontology aligning EU AI Act with AIRO + DPV

claude-plugin/    Claude Code plugin manifest + slash commands + MCP config
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

### OWASP APTS conformance

```python
from specter.apts import assess_self

report = assess_self()
print(f"Headline: {report.headline_score:.1%}  Tier: {report.headline_tier}")
print(f"Counts: {report.counts}")
# → Headline: 73.5%  Tier: None
# → {'total': 173, 'satisfied': 95, 'partial': 52, 'gap': 26, ...}
```

A frozen [self-conformance report](docs/evals/apts-self-conformance.md) is shipped as a reference baseline.

## What's intentionally *not* here

This is the **slice** that ports cleanly. The full commercial platform also ships:

- A 24-dimension × 139-question maturity-assessment knowledge base
- A roadmap-task registry + autoresearch refinement loop (the `ComplianceRewardHackDetector` is the judge; the loop itself stays proprietary)
- A Neo4j-backed Graph RAG retriever (this OSS package ships a stub; you bring your own)
- An evidence chain with WORM/Object Lock semantics
- Stripe billing, multi-tenant auth, audit reports, scanner agents

The slice you have here is what you need to **verify regulator-grounded outputs** and **evaluate your own pipeline against a reproducible baseline**.

## Provenance

- **`data/articles_existence`** + **`data/articles_requirements`** — original work; canonical EU AI Act catalog
- **`data/taxonomy`** — original implementation of the four-axis compound-risk taxonomy from *AI Agents Under EU Law* (working paper, 7 April 2026, §10.4)
- **`data/atlas`** + **`data/owasp_aix`** + **`data/crosswalk`** — vendored snapshots of MITRE ATLAS (Apache 2.0) and OWASP AI Exchange (CC0); see [LICENSE](LICENSE)
- **`apts/`** — original conformance engine over the vendored OWASP APTS v0.1.0 catalog (CC BY-SA 4.0)
- **`judge/reward_hack`** — original `ComplianceRewardHackDetector` adapted from the upstream Karpathy-style autoresearch loop
- **`judge/three_agent`** — adapted from the upstream sycophancy-weaponization architecture
- **`qa/`** + **`api/qa_route`** — Q&A endpoint adapted from the upstream public-tier partner integration; rate-limit semantics and closed-world refusal preserved verbatim

## Status

`v0.1.1` — public surface stable and end-to-end-verified. Expect breaking changes through `0.x` as the API converges; lock to a specific minor version in production.

## License

MIT for original code; vendored standards keep their upstream licenses (see [LICENSE](LICENSE)).
