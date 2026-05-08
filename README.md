# Specter

> EU AI Act compliance toolkit — ontology, taxonomy, LLM-as-Judge, grounded Q&A. Ships as a Python library and a Claude Code plugin.

```bash
pip install specter                # core: data + LLM-as-Judge
pip install 'specter[api]'         # adds FastAPI router for grounded Q&A
pip install 'specter[plugin]'      # adds MCP SDK for the Claude Code plugin
```

## Why this exists

- **Ground LLM output against the regulation.** Every reference is validated against a frozen 113-article + 13-annex catalog of Regulation (EU) 2024/1689 — hallucinated articles never reach the wire.
- **Catch reward-hacking in compliance roadmaps.** Six-check `ComplianceRewardHackDetector` (LLM-as-Judge) screens proposed remediation tasks for plagiarism, KB-reality violations, coverage-plausibility breaks, contract-completeness gaps, and rebutted-excuse matches. The detector OWNS the `origin` label — an agent that lies and self-labels as `agent_novel` when it actually plagiarised a prior task is caught by SequenceMatcher, not trusted on its self-report.
- **Surface a regulator-defensible taxonomy.** Four-axis agentic-AI compound-risk classification (cascading / emergent / attribution / temporal) anchored to EU AI Act articles + KB maturity dimensions, grounded in *AI Agents Under EU Law* (working paper, 7 April 2026).

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
pip install 'specter[plugin]>=0.1.2'

# From a checkout of the repo:
claude plugins install ./claude-plugin

# Or from the public GitHub:
claude plugins install github:Peaky8linders/specter-oss/claude-plugin
```

Restart Claude Code, then in any session:

```
/specter:check-article ref="Art. 13(1)(a)"
/specter:taxonomy
/specter:role-obligations role="deployer"
```

6 slash commands, 6 MCP tools. Full docs in [claude-plugin/README.md](claude-plugin/README.md).

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
├── api/          FastAPI router exposing POST /v1/eu-ai-act/ask with
│                 pluggable retriever
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

## Status

`v0.1.2` — public surface stable and end-to-end-verified. Expect breaking changes through `0.x` as the API converges; lock to a specific minor version in production.

## License

MIT (see [LICENSE](LICENSE)).
