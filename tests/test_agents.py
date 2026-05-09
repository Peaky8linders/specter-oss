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
    PersonaCustomisation,
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
    # Tests pass ``bridge=False`` so the orchestrator never spins up a
    # default ``MikeOSSBridge`` that probes localhost:3000. The bridge
    # default-on behaviour itself is exercised by dedicated tests below.
    return CaseOrchestrator(memory=memory, bridge=False)


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


# ─── Default-on Mike-OSS bridge ───────────────────────────────────────────


def test_orchestrator_constructs_default_bridge(monkeypatch) -> None:
    """No bridge kwarg → orchestrator builds one pointed at MIKE_OSS_BASE_URL."""
    monkeypatch.delenv("SPECTER_MIKE_BRIDGE", raising=False)
    monkeypatch.setenv("MIKE_OSS_BASE_URL", "http://127.0.0.1:1")
    orch = CaseOrchestrator()
    assert orch._bridge is not None
    assert isinstance(orch._bridge, MikeOSSBridge)
    assert orch._bridge._base_url == "http://127.0.0.1:1"


@pytest.mark.parametrize("toggle", ["off", "0", "false", "no", "OFF", " False "])
def test_orchestrator_skips_bridge_when_env_disables(toggle, monkeypatch) -> None:
    """Common ``off``-style env values disable the default bridge."""
    monkeypatch.setenv("SPECTER_MIKE_BRIDGE", toggle)
    orch = CaseOrchestrator()
    assert orch._bridge is None


def test_orchestrator_explicit_bridge_false_skips_default() -> None:
    """``bridge=False`` always skips, regardless of env state."""
    orch = CaseOrchestrator(bridge=False)
    assert orch._bridge is None


# ─── Persona customisation: schema + soft-fail paths ─────────────────────


def test_persona_customisation_without_key_falls_through(orchestrator) -> None:
    """A custom system_prompt with no api_key → deterministic claim wins."""
    case = CaseFile(
        question="What does Article 13 require?",
        role="provider",
        persona_customisations={
            Voice.MIKE: PersonaCustomisation(
                system_prompt="You are Mike Ross. Speak only in haiku.",
                # Note: no provider, no api_key — orchestrator should
                # NOT call any LLM and the deterministic line stands.
            ),
        },
    )
    dialogue = orchestrator.work(case)
    mike = next(t for t in dialogue.turns if t.speaker == Voice.MIKE)
    # The deterministic Mike claim leads with "Got it." or "I remember"
    # — never with a haiku. Pin one of the canonical openers.
    assert any(
        mike.claim.startswith(prefix)
        for prefix in ("Got it.", "I remember", "Nothing on file.")
    ), f"Expected deterministic claim; got: {mike.claim!r}"


def test_persona_customisation_invokes_llm_when_key_present(memory, monkeypatch) -> None:
    """system_prompt + provider + api_key → orchestrator routes to the LLM."""
    captured: dict[str, str] = {}

    # Stub the persona LLM helper so the test never makes a real call.
    from specter.agents import case as case_module

    def fake_call(*, provider, api_key, model, system, user):
        captured["provider"] = provider
        captured["api_key"] = api_key
        captured["model"] = model or ""
        captured["system"] = system
        captured["user"] = user
        return "Litt up!! That's NOT how Article 13 works, Ross."

    monkeypatch.setattr(case_module, "_call_persona_llm", fake_call)

    orch = CaseOrchestrator(memory=memory, bridge=False)
    case = CaseFile(
        question="What does Article 13 require?",
        role="provider",
        persona_customisations={
            Voice.LOUIS: PersonaCustomisation(
                system_prompt="You are Louis Litt at his most bombastic.",
                provider="claude",
                api_key="sk-ant-stub",
                model="claude-haiku-4-5-20251001",
            ),
        },
    )
    dialogue = orch.work(case)

    louis = next(t for t in dialogue.turns if t.speaker == Voice.LOUIS)
    assert louis.claim.startswith("Litt up!!"), (
        f"Expected the LLM-driven claim; got: {louis.claim!r}"
    )
    # The stub captured the resolved kwargs — confirm we routed to
    # the right provider / key / model.
    assert captured["provider"] == "claude"
    assert captured["api_key"] == "sk-ant-stub"
    assert captured["model"] == "claude-haiku-4-5-20251001"
    # System prompt is the user's custom personality.
    assert "Litt at his most bombastic" in captured["system"]
    # User prompt carries the case + the deterministic seed line so
    # the LLM has full context.
    assert "Article 13" in captured["user"]


def test_persona_customisation_llm_error_falls_back_to_deterministic(
    memory, monkeypatch,
) -> None:
    """Empty LLM reply → deterministic claim is preserved."""
    from specter.agents import case as case_module

    monkeypatch.setattr(
        case_module, "_call_persona_llm",
        lambda **_: "",  # simulate provider error / empty reply
    )

    orch = CaseOrchestrator(memory=memory, bridge=False)
    case = CaseFile(
        question="What does Article 13 require?",
        role="provider",
        persona_customisations={
            Voice.LOUIS: PersonaCustomisation(
                system_prompt="custom",
                provider="claude",
                api_key="sk-ant-stub",
            ),
        },
    )
    dialogue = orch.work(case)
    louis = next(t for t in dialogue.turns if t.speaker == Voice.LOUIS)
    # Falls through to the deterministic Louis line — either an
    # objection ("OBJECTION!"), a concession ("Fine, Ross."), or the
    # muted thought-cloud line.
    assert louis.claim.startswith("OBJECTION!") or louis.claim.startswith("Fine, Ross.")


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
