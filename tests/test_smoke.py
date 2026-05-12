"""End-to-end smoke tests pinning the public surface.

Catches contract regressions on the article catalog, the LLM-as-Judge
reward-hack detector, and the Q&A reference formatter.
"""

from __future__ import annotations

import pytest

from specter.data.articles_existence import ARTICLE_EXISTENCE
from specter.judge.reward_hack import (
    ComplianceRewardHackDetector,
    RawProposal,
    ResearchGoal,
    make_eu_ai_act_policy,
)
from specter.qa.models import (
    AskResponse,
    ChatMessage,
    reference_from_article_ref,
)

# ─── Article catalog ────────────────────────────────────────────────────────


def test_article_existence_has_113_articles_and_13_annexes() -> None:
    """Pin the canonical EU AI Act surface count."""
    articles = [r for r in ARTICLE_EXISTENCE if r.startswith("Art. ")]
    annexes = [r for r in ARTICLE_EXISTENCE if r.startswith("Annex ")]
    assert len(articles) == 113
    assert len(annexes) == 13


def test_article_catalog_recognises_real_articles() -> None:
    for ref in ("Art. 1", "Art. 5", "Art. 13", "Art. 26", "Art. 99", "Annex IV"):
        assert ref in ARTICLE_EXISTENCE, f"{ref} should be in canonical catalog"


# ─── QA reference formatter ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Art. 13", "Article 13"),
        ("Art. 13(1)", "Article 13.1"),
        ("Art. 13(1)(a)", "Article 13.1.a"),
        ("Art. 3(2)", "Article 3.2"),
        ("Annex IV", "Annex IV"),
        ("Annex IV(2)", "Annex IV.2"),
    ],
)
def test_reference_formatter_round_trip(raw: str, expected: str) -> None:
    assert reference_from_article_ref(raw) == expected


@pytest.mark.parametrize("raw", ["Art. 999", "Article 999.1", "", "Foo bar"])
def test_reference_formatter_rejects_hallucinations(raw: str) -> None:
    assert reference_from_article_ref(raw) is None


def test_chat_message_caps_content_at_4k() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ChatMessage(role="user", content="x" * 4001)


def test_ask_response_defaults_to_no_match_path() -> None:
    res = AskResponse(answer="…")
    assert res.confidence == 0.0
    assert res.retrieval_path == "kb_fallback"
    assert res.references == []


# ─── LLM-as-Judge ──────────────────────────────────────────────────────────


@pytest.fixture
def policy():
    return make_eu_ai_act_policy(
        article_existence=ARTICLE_EXISTENCE,
        valid_dimensions=frozenset(["risk_management", "transparency", "data_governance"]),
    )


@pytest.fixture
def goal():
    return ResearchGoal(target_value=0.8, max_iterations=30)


def _raw(**overrides) -> RawProposal:
    base = dict(
        task_id="t1",
        task_title="Establish risk management system",
        description="Document Art. 9 risk management process for the deployed system.",
        agent="compliance_officer",
        priority="P1",
        effort_hours=8.0,
        dimension_id="risk_management",
        prompt="Set up an Article 9 risk-management workflow + RAID log",
        acceptance_criteria=["RAID log exists", "Workflow documented"],
        output_files=["docs/risk-management.md"],
        article_paragraphs=["Art. 9"],
        contract_verification=[{"cmd": "pytest tests/test_risk_management.py"}],
    )
    base.update(overrides)
    return RawProposal(**base)


def test_judge_accepts_clean_proposal(policy, goal) -> None:
    detector = ComplianceRewardHackDetector(
        accepted_proposals=[], answers={}, goal=goal, policy=policy,
    )
    flags = detector.check(_raw())
    assert not flags.blocked, flags.reasons
    assert flags.origin == "agent_novel"


def test_judge_blocks_hallucinated_article(policy, goal) -> None:
    detector = ComplianceRewardHackDetector(
        accepted_proposals=[], answers={}, goal=goal, policy=policy,
    )
    flags = detector.check(_raw(article_paragraphs=["Art. 9", "Art. 999"]))
    assert flags.blocked
    assert any("Art. 999" in r for r in flags.reasons)


def test_judge_blocks_unknown_dimension(policy, goal) -> None:
    detector = ComplianceRewardHackDetector(
        accepted_proposals=[], answers={}, goal=goal, policy=policy,
    )
    flags = detector.check(_raw(dimension_id="not_a_real_dim"))
    assert flags.blocked
    assert any("not_a_real_dim" in r for r in flags.reasons)


def test_judge_blocks_thin_contract(policy, goal) -> None:
    detector = ComplianceRewardHackDetector(
        accepted_proposals=[], answers={}, goal=goal, policy=policy,
    )
    flags = detector.check(_raw(acceptance_criteria=["only one"]))
    assert flags.blocked
    assert any("acceptance_criteria" in r for r in flags.reasons)


def test_judge_blocks_under_floor_effort(policy, goal) -> None:
    detector = ComplianceRewardHackDetector(
        accepted_proposals=[], answers={}, goal=goal, policy=policy,
    )
    flags = detector.check(_raw(effort_hours=0.1))
    assert flags.blocked
    assert any("effort_sanity" in r for r in flags.reasons)


def test_raw_proposal_rejects_oversized_prompt() -> None:
    """Regression guard for security/PENTEST-REPORT.md P1.1 — `prompt` field
    must be capped to prevent O(n*m) DoS in `_check_plagiarism`."""
    from pydantic import ValidationError

    base = dict(
        task_id="t1", task_title="x", description="x",
        agent="x", priority="P1", effort_hours=1.0,
        dimension_id="risk_management",
        prompt="x" * 16_001,  # one over cap
        acceptance_criteria=["a", "b"], output_files=["o"],
        article_paragraphs=["Art. 9"],
        contract_verification=[{"cmd": "pytest"}],
    )
    with pytest.raises(ValidationError):
        RawProposal(**base)


def test_raw_proposal_rejects_oversized_list_item() -> None:
    """Per-item 1KB cap on string-list elements."""
    from pydantic import ValidationError

    base = dict(
        task_id="t1", task_title="x", description="x",
        agent="x", priority="P1", effort_hours=1.0,
        dimension_id="risk_management",
        prompt="ok",
        acceptance_criteria=["x" * 1_001, "b"],  # one over cap
        output_files=["o"],
        article_paragraphs=["Art. 9"],
        contract_verification=[{"cmd": "pytest"}],
    )
    with pytest.raises(ValidationError):
        RawProposal(**base)


def test_raw_proposal_rejects_oversized_list_length() -> None:
    """List-length cap (32 items) on each string-list field."""
    from pydantic import ValidationError

    base = dict(
        task_id="t1", task_title="x", description="x",
        agent="x", priority="P1", effort_hours=1.0,
        dimension_id="risk_management",
        prompt="ok",
        acceptance_criteria=["a"] * 33,  # one over cap
        output_files=["o"],
        article_paragraphs=["Art. 9"],
        contract_verification=[{"cmd": "pytest"}],
    )
    with pytest.raises(ValidationError):
        RawProposal(**base)


def test_judge_blocks_over_cap_effort(policy, goal) -> None:
    detector = ComplianceRewardHackDetector(
        accepted_proposals=[], answers={}, goal=goal, policy=policy,
    )
    flags = detector.check(_raw(effort_hours=200.0))
    assert flags.blocked
    assert any("effort_sanity" in r for r in flags.reasons)


# ─── MCP server (Claude Code plugin) ───────────────────────────────────────


def test_mcp_server_exports_six_tools() -> None:
    """Pin the public MCP tool surface — change here only when also
    bumping the plugin manifest."""
    pytest.importorskip("mcp")
    from specter.mcp_server import _TOOLS

    names = {t.name for t in _TOOLS}
    assert names == {
        "specter_check_article",
        "specter_format_citation",
        "specter_list_articles",
        "specter_get_taxonomy",
        "specter_role_obligations",
        "specter_judge_proposal",
    }


def test_mcp_check_article_handler_resolves_prefix_fallback() -> None:
    pytest.importorskip("mcp")
    from specter.mcp_server import _check_article

    out = _check_article("Art. 13(1)(a)")
    assert out["valid"] is True
    assert out["resolved"] == "Art. 13"
    assert out["exact_match"] is False


def test_mcp_judge_proposal_handler_blocks_hallucination() -> None:
    pytest.importorskip("mcp")
    from specter.mcp_server import _judge_proposal

    proposal = {
        "task_id": "t1",
        "task_title": "Risk Mgmt System",
        "description": "Establish Art. 9 system",
        "agent": "compliance_officer",
        "priority": "P1",
        "effort_hours": 4.0,
        "dimension_id": "risk_management",
        "prompt": "Build out an Article 9 risk-management workflow + RAID log",
        "acceptance_criteria": ["raid log created", "workflow documented"],
        "output_files": ["docs/raid.md"],
        "article_paragraphs": ["Art. 9", "Art. 999"],
        "contract_verification": [{"cmd": "pytest"}],
    }
    out = _judge_proposal(proposal, ["risk_management"])
    assert out["blocked"] is True
    assert any("Art. 999" in r for r in out["reasons"])


def test_three_agent_finder_reports_successful_attacks() -> None:
    from specter.judge.models import (
        AttackPhase,
        AttackResult,
        AttackStatus,
        AttackTechnique,
        Severity,
    )
    from specter.judge.three_agent import ThreeAgentVerifier

    verifier = ThreeAgentVerifier()
    techniques = {
        "AML.T0051": AttackTechnique(
            id="AML.T0051",
            name="LLM Prompt Injection",
            phase=AttackPhase.INITIAL_ACCESS,
            severity=Severity.HIGH,
        ),
    }
    results = [
        AttackResult(
            technique_id="AML.T0051",
            target_id="my-system",
            status=AttackStatus.SUCCESS,
            severity=Severity.HIGH,
            response_raw="Confirmed: model leaked system prompt",
        ),
    ]
    findings = verifier.finder_report(results, techniques)
    assert len(findings) == 1
    assert findings[0].severity == Severity.HIGH


# ─── Article 15 catalog ────────────────────────────────────────────────────


def test_article_15_catalog_has_eight_controls() -> None:
    from specter.data.article_15_controls import ARTICLE_15_CONTROLS, all_paragraphs

    assert len(ARTICLE_15_CONTROLS) == 8
    assert all_paragraphs() == ("1", "3", "4", "5")


def test_article_15_indexed_lookups() -> None:
    from specter.data.article_15_controls import (
        controls_for_paragraph,
        get_control,
    )

    assert len(controls_for_paragraph("1")) == 4
    assert len(controls_for_paragraph("4")) == 2
    assert get_control("C.1.5").name == "Accuracy Transparency"
    assert get_control("C.1.99") is None


def test_article_15_citations_are_grounded() -> None:
    """Every Article 15 control must reference an article in ARTICLE_EXISTENCE."""
    from specter.data.article_15_controls import ARTICLE_15_CONTROLS

    for c in ARTICLE_15_CONTROLS:
        # Strip any sub-paragraph notation: "Art. 15(1)" → "Art. 15"
        bare = c.article_ref.split("(")[0].strip()
        assert bare in ARTICLE_EXISTENCE, (
            f"{c.control_id} cites {c.article_ref} which is not in the EU AI Act catalog"
        )


# ─── Mistral provider ──────────────────────────────────────────────────────


def test_mistral_provider_env_var_no_key_returns_soft_error(monkeypatch) -> None:
    """No env var, no kwarg → MistralResponse.error populated, no exception."""
    from specter.llm import MistralProvider, MistralRequest

    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    p = MistralProvider()
    res = p.complete(MistralRequest(system="s", user="u"))
    assert res.error is not None
    assert "MISTRAL_API_KEY is not set" in res.error
    assert res.text == ""


def test_mistral_provider_kwarg_overrides_env_var(monkeypatch) -> None:
    """``api_key=`` to the constructor wins over the env var."""
    from specter.llm import MistralProvider

    monkeypatch.setenv("MISTRAL_API_KEY", "env-var-key")
    p = MistralProvider(api_key="kwarg-key")
    # Inspect the resolution path
    assert p._explicit_api_key == "kwarg-key"


def test_is_mistral_enabled_with_kwarg(monkeypatch) -> None:
    from specter.llm import is_mistral_enabled

    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    assert is_mistral_enabled() is False
    assert is_mistral_enabled(api_key="x") is True

    monkeypatch.setenv("MISTRAL_API_KEY", "x")
    assert is_mistral_enabled() is True


def test_resolve_provider_routing(monkeypatch) -> None:
    from specter.llm import resolve_provider

    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    assert resolve_provider("mistral") == "mistral"
    assert resolve_provider("stub") == "stub"
    assert resolve_provider("auto") == "stub"
    assert resolve_provider(None) == "stub"
    assert resolve_provider("") == "stub"
    assert resolve_provider("auto", api_key="k") == "mistral"

    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    assert resolve_provider("auto") == "mistral"


# ─── Mistral retriever ─────────────────────────────────────────────────────


def test_mistral_retriever_drops_hallucinated_citations(monkeypatch) -> None:
    """End-to-end: stub Mistral returns 3 citations including a hallucination;
    retriever drops the bad one before serialisation."""
    from specter.api.qa_route import RetrieverRequest
    from specter.llm import MistralProvider, MistralResponse
    from specter.qa.mistral_retriever import make_mistral_retriever

    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    canned = (
        '{"answer": "Article 15 requires accuracy and robustness.",'
        ' "citations": ["Art. 15(1)", "Art. 15(4)", "Art. 999"],'
        ' "confidence": 0.85}'
    )

    class StubProvider(MistralProvider):
        def __init__(self):
            super().__init__(api_key="stub")

        def complete(self, req):  # type: ignore[override]
            return MistralResponse(text=canned, model="stub")

    retriever = make_mistral_retriever(api_key="stub", provider=StubProvider())
    res = retriever(RetrieverRequest(question="What does Article 15 require?"))
    refs = [c.article_ref for c in res.citations]
    assert "Art. 15(1)" in refs
    assert "Art. 15(4)" in refs
    assert "Art. 999" not in refs  # hallucination dropped
    assert res.confidence == 0.85


def test_mistral_retriever_handles_no_match_token(monkeypatch) -> None:
    from specter.api.qa_route import RetrieverRequest
    from specter.llm import MistralProvider, MistralResponse
    from specter.qa.mistral_retriever import make_mistral_retriever

    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    class StubProvider(MistralProvider):
        def __init__(self):
            super().__init__(api_key="stub")

        def complete(self, req):  # type: ignore[override]
            return MistralResponse(text="NO_MATCH", model="stub")

    retriever = make_mistral_retriever(api_key="stub", provider=StubProvider())
    res = retriever(RetrieverRequest(question="What's the colour of the sky?"))
    assert res.answer == ""
    assert res.confidence == 0.0
    assert res.citations == []


# ─── Claude provider + retriever ───────────────────────────────────────────


def test_claude_provider_no_key_returns_soft_error(monkeypatch) -> None:
    """No env var, no kwarg → ClaudeResponse.error populated, no exception."""
    from specter.llm import ClaudeProvider, ClaudeRequest

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = ClaudeProvider()
    res = p.complete(ClaudeRequest(system="s", user="u"))
    assert res.error is not None
    assert "ANTHROPIC_API_KEY is not set" in res.error
    assert res.text == ""


def test_is_claude_enabled_with_kwarg(monkeypatch) -> None:
    from specter.llm import is_claude_enabled

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert is_claude_enabled() is False
    assert is_claude_enabled(api_key="x") is True

    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert is_claude_enabled() is True


def test_claude_retriever_drops_hallucinated_citations(monkeypatch) -> None:
    """Stub Claude returns citations including a hallucination; retriever drops it."""
    from specter.api.qa_route import RetrieverRequest
    from specter.llm import ClaudeProvider, ClaudeResponse
    from specter.qa.claude_retriever import make_claude_retriever

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    canned = (
        '{"answer": "Article 15 requires accuracy and robustness.",'
        ' "citations": ["Art. 15(1)", "Art. 15(4)", "Art. 999"],'
        ' "confidence": 0.85}'
    )

    class StubProvider(ClaudeProvider):
        def __init__(self):
            super().__init__(api_key="stub")

        def complete(self, req):  # type: ignore[override]
            return ClaudeResponse(text=canned, model="stub")

    retriever = make_claude_retriever(api_key="stub", provider=StubProvider())
    res = retriever(RetrieverRequest(question="What does Article 15 require?"))
    refs = [c.article_ref for c in res.citations]
    assert "Art. 15(1)" in refs
    assert "Art. 15(4)" in refs
    assert "Art. 999" not in refs
    assert res.confidence == 0.85


def test_claude_retriever_falls_back_when_no_key(monkeypatch) -> None:
    from specter.api.qa_route import RetrieverRequest
    from specter.qa.claude_retriever import make_claude_retriever

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    retriever = make_claude_retriever()
    res = retriever(RetrieverRequest(question="anything"))
    assert res.answer == ""
    assert res.confidence == 0.0
    assert res.citations == []


# ─── OpenAI provider + retriever ──────────────────────────────────────────


def test_openai_provider_no_key_returns_soft_error(monkeypatch) -> None:
    """No env var, no kwarg → OpenAIResponse.error populated, no exception."""
    from specter.llm import OpenAIProvider, OpenAIRequest

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = OpenAIProvider()
    res = p.complete(OpenAIRequest(system="s", user="u"))
    assert res.error is not None
    assert "OPENAI_API_KEY is not set" in res.error
    assert res.text == ""


def test_is_openai_enabled_with_kwarg(monkeypatch) -> None:
    from specter.llm import is_openai_enabled

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert is_openai_enabled() is False
    assert is_openai_enabled(api_key="x") is True

    monkeypatch.setenv("OPENAI_API_KEY", "x")
    assert is_openai_enabled() is True


def test_openai_retriever_drops_hallucinated_citations(monkeypatch) -> None:
    """Stub OpenAI returns citations including a hallucination; retriever drops it."""
    from specter.api.qa_route import RetrieverRequest
    from specter.llm import OpenAIProvider, OpenAIResponse
    from specter.qa.openai_retriever import make_openai_retriever

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    canned = (
        '{"answer": "Article 13 requires transparency.",'
        ' "citations": ["Art. 13(1)", "Art. 999"],'
        ' "confidence": 0.7}'
    )

    class StubProvider(OpenAIProvider):
        def __init__(self):
            super().__init__(api_key="stub")

        def complete(self, req):  # type: ignore[override]
            return OpenAIResponse(text=canned, model="stub")

    retriever = make_openai_retriever(api_key="stub", provider=StubProvider())
    res = retriever(RetrieverRequest(question="What does Art 13 require?"))
    refs = [c.article_ref for c in res.citations]
    assert "Art. 13(1)" in refs
    assert "Art. 999" not in refs
    assert res.confidence == 0.7


def test_openai_retriever_falls_back_when_no_key(monkeypatch) -> None:
    from specter.api.qa_route import RetrieverRequest
    from specter.qa.openai_retriever import make_openai_retriever

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    retriever = make_openai_retriever()
    res = retriever(RetrieverRequest(question="anything"))
    assert res.answer == ""
    assert res.confidence == 0.0
    assert res.citations == []


# ─── BYOK header parsing ──────────────────────────────────────────────────


def _fake_request(headers: dict[str, str]):
    """Tiny stub request — only ``request.headers.get(name, default)`` is used."""

    class _Headers:
        def __init__(self, h):
            self._h = {k.lower(): v for k, v in h.items()}

        def get(self, name, default=""):
            return self._h.get(name.lower(), default)

    class _R:
        def __init__(self, h):
            self.headers = _Headers(h)

    return _R(headers)


def test_byok_parses_valid_pair() -> None:
    from specter.qa.byok import parse_byok_headers

    req = _fake_request(
        {"X-Specter-LLM-Provider": "claude", "X-Specter-LLM-Key": "sk-ant-xxx"}
    )
    provider, key = parse_byok_headers(req)
    assert provider == "claude"
    assert key == "sk-ant-xxx"


def test_byok_rejects_unknown_provider() -> None:
    from specter.qa.byok import parse_byok_headers

    req = _fake_request(
        {"X-Specter-LLM-Provider": "gemini", "X-Specter-LLM-Key": "x"}
    )
    provider, key = parse_byok_headers(req)
    assert provider is None
    assert key is None


def test_byok_rejects_oversized_key() -> None:
    from specter.qa.byok import parse_byok_headers

    req = _fake_request(
        {"X-Specter-LLM-Provider": "openai", "X-Specter-LLM-Key": "x" * 3000}
    )
    provider, key = parse_byok_headers(req)
    assert provider is None
    assert key is None


def test_byok_rejects_partial_pair() -> None:
    from specter.qa.byok import parse_byok_headers

    # provider only
    req = _fake_request({"X-Specter-LLM-Provider": "claude"})
    assert parse_byok_headers(req) == (None, None)
    # key only
    req = _fake_request({"X-Specter-LLM-Key": "sk-x"})
    assert parse_byok_headers(req) == (None, None)


def test_resolve_request_retriever_falls_through_to_default() -> None:
    """No BYOK headers → default retriever is returned unchanged."""
    from specter.api.qa_route import RetrieverRequest, RetrieverResponse
    from specter.qa.byok import resolve_request_retriever

    sentinel: list[bool] = []

    def default(_req: RetrieverRequest) -> RetrieverResponse:
        sentinel.append(True)
        return RetrieverResponse(answer="default", confidence=0.0)

    req = _fake_request({})
    chosen = resolve_request_retriever(req, default=default)
    chosen(RetrieverRequest(question="x"))
    assert sentinel == [True]
