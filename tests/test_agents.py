"""Behaviour tests for the Suits-themed multi-agent overlay.

Pin the deterministic case orchestrator + persona catalog so the
FastAPI route and the comic-book front-end can ship without surprise
contract drift. All tests are network-free; the optional mike-oss
bridge is exercised against an unreachable URL to confirm graceful
fallthrough.
"""

from __future__ import annotations

import re

import pytest

from specter.agents import (
    PERSONAS,
    CaseDialogue,
    CaseFile,
    CaseOrchestrator,
    Citation,
    MikeMemory,
    MikeOSSBridge,
    Turn,
    Voice,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def memory(tmp_path) -> MikeMemory:
    """Per-test memory file under ``tmp_path`` — never touch the user's home."""
    return MikeMemory(path=tmp_path / "mike_memory.json")


@pytest.fixture
def orchestrator(memory) -> CaseOrchestrator:
    return CaseOrchestrator(memory=memory)


# ─── Persona catalog ──────────────────────────────────────────────────────


_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def test_personas_have_required_fields() -> None:
    """All five voices in PERSONAS (Harvey is the mascot), hex colours
    well-formed, prompts non-empty."""
    assert set(PERSONAS) == {
        Voice.HARVEY,
        Voice.MIKE,
        Voice.RACHEL,
        Voice.LOUIS,
        Voice.JESSICA,
    }
    for voice, persona in PERSONAS.items():
        assert persona.voice == voice
        assert persona.name.strip()
        assert persona.title.strip()
        assert persona.catchphrase.strip()
        assert persona.system_prompt.strip()
        assert _HEX_RE.match(persona.color), f"{voice}: bad primary hex {persona.color!r}"
        assert _HEX_RE.match(persona.accent_color), (
            f"{voice}: bad accent hex {persona.accent_color!r}"
        )


# ─── Five-turn pipeline ───────────────────────────────────────────────────


def test_orchestrator_returns_four_unique_speakers_in_order(orchestrator) -> None:
    """Turns are Rachel → Mike → Louis → Rachel → Jessica and all four
    *working* voices appear (Harvey is the mascot — not in the dialogue)."""
    case = CaseFile(question="What does Article 13 require?", role="provider")
    dialogue = orchestrator.work(case)

    assert isinstance(dialogue, CaseDialogue)
    assert len(dialogue.turns) == 5
    expected = [Voice.RACHEL, Voice.MIKE, Voice.LOUIS, Voice.RACHEL, Voice.JESSICA]
    assert [t.speaker for t in dialogue.turns] == expected
    # Sanity: all four working voices are represented; Harvey stays off-stage.
    speakers_in_dialogue = {t.speaker for t in dialogue.turns}
    assert speakers_in_dialogue == {Voice.RACHEL, Voice.MIKE, Voice.LOUIS, Voice.JESSICA}
    assert Voice.HARVEY not in speakers_in_dialogue


def test_mike_cites_role_obligations(orchestrator) -> None:
    """Question + role=deployer surfaces at least one Art. 26/27/29 reference."""
    case = CaseFile(question="What must I do as a deployer?", role="deployer")
    dialogue = orchestrator.work(case)

    mike_turn = next(t for t in dialogue.turns if t.speaker == Voice.MIKE)
    cited = {c.article_ref for c in mike_turn.citations}

    deployer_articles = {
        "Article 26",
        "Article 27",
        "Article 29",
    }
    # Role obligations include Art. 26/27 directly; either is sufficient
    # to confirm role wiring.
    assert cited & deployer_articles, (
        f"Mike should cite a deployer obligation; got {sorted(cited)}"
    )


# ─── Louis behaviour ──────────────────────────────────────────────────────


def test_louis_objects_when_mike_cites_nothing_useful(orchestrator) -> None:
    """Off-topic question with no role → Louis fires the objection panel."""
    case = CaseFile(
        question="Tell me about purple monkey dishwashers",
        role=None,
    )
    dialogue = orchestrator.work(case)

    louis_turn = next(t for t in dialogue.turns if t.speaker == Voice.LOUIS)
    assert "objection" in louis_turn.flags, (
        f"Expected Louis to object; got flags={louis_turn.flags}"
    )


def test_louis_quiets_when_mike_cites_many_valid_refs(orchestrator) -> None:
    """Provider role → Mike floods the panel with valid refs → Louis backs down."""
    case = CaseFile(
        question="What are my high-risk obligations as a provider?",
        role="provider",
    )
    dialogue = orchestrator.work(case)

    mike_turn = next(t for t in dialogue.turns if t.speaker == Voice.MIKE)
    louis_turn = next(t for t in dialogue.turns if t.speaker == Voice.LOUIS)

    # Sanity guard for the precondition the test name describes.
    assert len(mike_turn.citations) >= 3, (
        f"Test precondition: Mike should cite ≥3 valid refs for provider/high-risk; "
        f"got {len(mike_turn.citations)}"
    )
    assert "objection" not in louis_turn.flags
    assert louis_turn.confidence < 0.5


# ─── Jessica's verdict ────────────────────────────────────────────────────


def test_jessica_verdict_is_dialogue_verdict(orchestrator) -> None:
    """Last panel is Jessica's; her claim equals the dialogue verdict."""
    case = CaseFile(question="What does Article 15 require?", role="provider")
    dialogue = orchestrator.work(case)

    last = dialogue.turns[-1]
    assert last.speaker == Voice.JESSICA
    assert dialogue.verdict == last.claim


# ─── Hallucination guard ──────────────────────────────────────────────────


def test_no_hallucinated_refs_in_output(orchestrator, monkeypatch) -> None:
    """Inject a fake article into Mike's recall; confirm it never reaches the wire."""
    from specter.agents import case as case_module

    real_recall = case_module.CaseOrchestrator._mike_recall

    def poisoned_recall(self, *, question, role):
        valid_refs, dropped_refs, snippets = real_recall(self, question=question, role=role)
        # Slip a hallucinated ref into the candidate list. The Citation
        # constructor (via reference_from_article_ref) MUST drop it.
        valid_refs = ["Art. 999"] + list(valid_refs)
        return valid_refs, list(dropped_refs), list(snippets)

    monkeypatch.setattr(
        case_module.CaseOrchestrator, "_mike_recall", poisoned_recall
    )

    case = CaseFile(question="What does Article 13 require?", role="provider")
    dialogue = orchestrator.work(case)

    # Article 999 must not appear in the dialogue's aggregated references.
    assert all("999" not in r for r in dialogue.references), (
        f"Hallucinated Art. 999 leaked: {dialogue.references}"
    )
    # ...nor in any citation on any turn.
    for turn in dialogue.turns:
        for cite in turn.citations:
            assert "999" not in cite.article_ref


# ─── Memory persistence ──────────────────────────────────────────────────


def test_memory_remembers_case_across_runs(orchestrator) -> None:
    """Running the same case twice → second run's Mike claim mentions remembering."""
    question = "What does Article 13 require?"
    first = orchestrator.work(CaseFile(question=question, role="provider"))
    second = orchestrator.work(CaseFile(question=question, role="provider"))

    # Same question → same case_id → memory hit on the second run.
    assert first.case_id == second.case_id

    second_mike = next(t for t in second.turns if t.speaker == Voice.MIKE)
    assert "remember" in second_mike.claim.lower(), (
        f"Mike should signal recall on a repeat case; got: {second_mike.claim!r}"
    )


# ─── Bridge fall-through ─────────────────────────────────────────────────


def test_mike_bridge_failure_falls_back_silently(memory) -> None:
    """Unreachable bridge URL → case completes without exceptions."""
    # Port 1 is reserved; nothing listens there. Tight 0.05s timeout
    # keeps the test fast even on a connection-refused fall-through.
    bridge = MikeOSSBridge(base_url="http://127.0.0.1:1", timeout=0.05)
    orch = CaseOrchestrator(memory=memory, bridge=bridge)

    dialogue = orch.work(CaseFile(question="What does Article 13 require?", role="provider"))

    assert len(dialogue.turns) == 5
    # The bridge should have probed and returned False; Mike's panel
    # should still carry the role-driven citations.
    mike_turn = next(t for t in dialogue.turns if t.speaker == Voice.MIKE)
    assert mike_turn.citations, "Bridge failure must not zero-out Mike's local recall."


# ─── Sanity guard for the wire shape ─────────────────────────────────────


def test_dialogue_models_are_serialisable() -> None:
    """The whole dialogue chain round-trips through Pydantic without surprise."""
    turn = Turn(
        speaker=Voice.MIKE,
        name="Mike Ross",
        claim="Test.",
        citations=[Citation(article_ref="Article 13")],
        confidence=0.5,
        flags=[],
        panel_kind="speech",
    )
    encoded = turn.model_dump()
    assert encoded["speaker"] == "mike"
    assert encoded["citations"][0]["article_ref"] == "Article 13"
