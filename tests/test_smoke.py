"""End-to-end smoke tests pinning the three core surfaces.

These tests exist to catch contract regressions on the public API and
to verify the LLM-as-Judge + Q&A reference formatter + APTS
self-conformance results match the upstream baselines.
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


def test_judge_blocks_over_cap_effort(policy, goal) -> None:
    detector = ComplianceRewardHackDetector(
        accepted_proposals=[], answers={}, goal=goal, policy=policy,
    )
    flags = detector.check(_raw(effort_hours=200.0))
    assert flags.blocked
    assert any("effort_sanity" in r for r in flags.reasons)


# ─── APTS conformance ──────────────────────────────────────────────────────


def test_apts_self_conformance_matches_upstream_baseline() -> None:
    """Pin the headline 73.5% baseline. If the curated evidence map
    changes, this test should be updated alongside the diff."""
    from specter.apts import assess_self

    report = assess_self()
    assert report.counts["total"] == 173
    # Allow ±2% drift; tighter than that would make this test brittle.
    assert 0.715 <= report.headline_score <= 0.755
    assert report.counts["satisfied"] >= 90
    assert report.counts["satisfied"] + report.counts["partial"] + report.counts["gap"] == 173


def test_apts_eight_domains() -> None:
    from specter.apts.requirements import list_domains

    assert len(list_domains()) == 8


def test_apts_three_tiers() -> None:
    from specter.apts.models import APTSTier

    assert {t.value for t in APTSTier} == {1, 2, 3}


# ─── 3-agent verifier ──────────────────────────────────────────────────────


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
