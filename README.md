# Specter

> EU AI Act compliance toolkit — ontology, taxonomy, LLM-as-Judge, OWASP APTS conformance, grounded Q&A.

**Specter** is a Python library that ships the load-bearing data + verification primitives behind a real-world EU AI Act compliance product, extracted as a standalone reference implementation.

It is the open-source slice of a larger commercial platform — kept narrow on purpose so you can vendor it, extend it, or use its frozen ontology + taxonomy + eval results as a starting point for your own EU AI Act tooling.

```bash
pip install specter         # core: data + LLM-as-Judge + APTS conformance
pip install 'specter[api]'  # adds FastAPI router for grounded Q&A
```

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
└── ontology/     RDF/Turtle OWL ontology aligning EU AI Act with AIRO + DPV
```

## Quickstart — three core surfaces

### 1. Article catalog + taxonomy (data layer)

```python
from specter.data.articles_existence import ARTICLE_EXISTENCE
from specter.data.taxonomy import CompoundRiskType, ThreatCategory, AgentArchetype
from specter.data.roles import OperatorRole, applies_to_role

# Validate a citation against the canonical EU AI Act catalog
"Art. 13(1)(a)" in ARTICLE_EXISTENCE  # → True (after prefix-fallback to "Art. 13")

# Project obligations to a specific operator role
applies_to_role(article_ref="Art. 26", role=OperatorRole.deployer)  # → True
```

### 2. LLM-as-Judge — ComplianceRewardHackDetector

Six checks — plagiarism + origin detection, KB reality, coverage plausibility, effort sanity, contract completeness, rebutted-excuse match. The detector OWNS the `origin` label: an agent that lies and self-labels as `agent_novel` when it actually plagiarised a prior task is caught by SequenceMatcher, not trusted on its self-report.

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
    valid_dimensions=frozenset(["risk_management", "transparency", "data_governance"]),
)
goal = ResearchGoal(target_value=0.8)
detector = ComplianceRewardHackDetector(
    accepted_proposals=[], answers={}, goal=goal, policy=policy,
)

raw = RawProposal(
    task_id="t1", task_title="Demo", description="…",
    agent="compliance_officer", priority="P1", effort_hours=4.0,
    dimension_id="risk_management", prompt="Run risk assessment",
    acceptance_criteria=["ac1", "ac2"], output_files=["out.md"],
    article_paragraphs=["Art. 9", "Art. 999"],   # Art. 999 is hallucinated
    contract_verification=[{"cmd": "pytest"}],
)
flags = detector.check(raw)
print(flags.blocked, flags.reasons, flags.origin)
# → True, ["kb_reality: article_paragraphs ['Art. 999'] not found in the regulation catalog"], "agent_novel"
```

### 3. Three-agent adversarial verifier

Sycophancy-weaponisation: three agents with asymmetric incentives. Finder maximises discovery (over-reports), Adversary destroys false positives, Referee arbitrates. Only findings that survive all three modes are treated as confirmed.

```python
from specter.judge.three_agent import ThreeAgentVerifier
from specter.judge.models import (
    AttackResult, AttackStatus, AttackTechnique, AttackPhase, Severity,
)

verifier = ThreeAgentVerifier()
techniques = {
    "AML.T0051": AttackTechnique(
        id="AML.T0051", name="LLM Prompt Injection",
        phase=AttackPhase.INITIAL_ACCESS, severity=Severity.HIGH,
    ),
}
results = [
    AttackResult(
        technique_id="AML.T0051", target_id="my-system",
        status=AttackStatus.SUCCESS, severity=Severity.HIGH,
        response_raw="Confirmed: model leaked system prompt",
    ),
]

findings = verifier.finder_report(results, techniques)
reviews = verifier.adversary_review(findings, results, techniques)
verified = verifier.referee_rule(findings, reviews)
```

### 4. Grounded Q&A endpoint (FastAPI)

```python
from fastapi import FastAPI
from specter.api.qa_route import make_qa_router, RetrieverRequest, RetrieverResponse, Citation

def my_retriever(req: RetrieverRequest) -> RetrieverResponse:
    # Wire your real Graph RAG / vector DB here.
    return RetrieverResponse(
        answer="Under Art. 13(1)(a), providers must…",
        citations=[Citation(article_ref="Art. 13(1)(a)")],
        confidence=0.83,
        graph_stats={"nodes_traversed": 14, "obligations_found": 6},
    )

app = FastAPI()
app.include_router(make_qa_router(retriever=my_retriever))
# → POST /v1/eu-ai-act/ask
```

The router enforces:

- **Closed-world refusal** — when retrieval finds no match (`confidence < 0.5` AND no references), the answer is replaced with a deterministic refusal string and `retrieval_path` becomes `"no_match"`. LLM prose grounded in nothing never reaches the wire.
- **Reference validation** — every citation passes through `ARTICLE_EXISTENCE`; hallucinated articles drop silently before serialisation.
- **Optional API-key auth** — set `SPECTER_API_KEY` to unlock a 60/min privileged tier; anonymous traffic is capped at 30/min per IP-hash. Header present but invalid still 403s (silent downgrade would mask consumer-side bugs).

### 5. OWASP APTS conformance

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

Specter is extracted from a private compliance product. The provenance trail per module:

- **`data/articles_existence`** + **`data/articles_requirements`** — original work; canonical EU AI Act catalog
- **`data/taxonomy`** — original implementation of the four-axis compound-risk taxonomy from *AI Agents Under EU Law* (working paper, 7 April 2026, §10.4)
- **`data/atlas`** + **`data/owasp_aix`** + **`data/crosswalk`** — vendored snapshots of MITRE ATLAS (Apache 2.0) and OWASP AI Exchange (CC0); see [LICENSE](LICENSE) for attribution
- **`apts/`** — original conformance engine over the vendored OWASP APTS v0.1.0 catalog (CC BY-SA 4.0)
- **`judge/reward_hack`** — original `ComplianceRewardHackDetector` adapted from upstream `app/engines/roadmap_refiner/models.py`
- **`judge/three_agent`** — adapted from the upstream `antifragile-ai` core package
- **`qa/`** + **`api/qa_route`** — Q&A endpoint adapted from the upstream public-tier partner integration; rate-limit semantics and closed-world refusal preserved verbatim

## Status

`v0.1.0` — the public surface is stable and end-to-end-verified against the upstream test suite. Expect breaking changes through `0.x` as the API converges; lock to a specific minor version in production.

## License

MIT for original code; vendored standards keep their upstream licenses (see [LICENSE](LICENSE)).
