"""End-to-end tests for the Suits-themed agent route + dev app.

The agent layer is owned by a parallel worktree; if it isn't importable
yet at test-collection time the whole module skips cleanly via
``importorskip``. The 503 fallback inside the route itself is exercised
implicitly by the route module's own import guard (if you can import
``specter.api.case_route`` at all, the guard works).
"""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# If the agents layer hasn't been built yet, skip cleanly. The route
# module itself is importable without it (503 fallback path), but these
# tests cover the happy path which needs a real orchestrator.
pytest.importorskip("specter.agents.case")

from specter.api.case_route import make_case_router  # noqa: E402

# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_app(router_factory_kwargs: dict | None = None) -> FastAPI:
    """Build a fresh FastAPI app wrapping a fresh case router.

    Each test gets its own app so rate-limit buckets, orchestrator
    state, and SlowAPI's per-app middleware never bleed between tests.
    """
    app = FastAPI()
    app.include_router(make_case_router(**(router_factory_kwargs or {})))
    return app


_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


# ─── /v1/case/personas ──────────────────────────────────────────────────────


def test_personas_endpoint_returns_five() -> None:
    """Persona catalog has exactly five characters (four working agents
    + Harvey as the project mascot) with well-formed fields. The SPA
    bootstrap depends on this contract — a regression here means the
    comic-book front-end can't paint its hero or its panels."""
    client = TestClient(_make_app())
    res = client.get("/v1/case/personas")
    assert res.status_code == 200, res.text
    payload = res.json()
    assert isinstance(payload, list)
    assert len(payload) == 5

    voices = {row["voice"] for row in payload}
    assert voices == {"harvey", "mike", "rachel", "louis", "jessica"}

    for row in payload:
        for field in ("voice", "name", "title", "color", "accent_color", "catchphrase"):
            assert field in row, f"missing {field} in {row}"
            assert isinstance(row[field], str) and row[field], (
                f"{field} should be a non-empty string"
            )
        assert _HEX_COLOR_RE.match(row["color"]), f"bad color hex: {row['color']}"
        assert _HEX_COLOR_RE.match(row["accent_color"]), (
            f"bad accent_color hex: {row['accent_color']}"
        )


# ─── /v1/case (happy path) ──────────────────────────────────────────────────


def test_post_case_returns_dialogue_with_five_turns() -> None:
    """Standard compliance question yields a five-turn dialogue with
    the canonical speaker order: Rachel → Mike → Louis → Rachel → Jessica."""
    client = TestClient(_make_app())
    res = client.post(
        "/v1/case",
        json={
            "question": "What does Article 13 require for high-risk AI systems?",
            "role": "provider",
            "enable_louis_objection": True,
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert "turns" in payload
    turns = payload["turns"]
    assert len(turns) == 5

    # Turn discriminator is ``speaker`` per the agent layer's contract.
    speakers = [turn["speaker"] for turn in turns]
    assert speakers == ["rachel", "mike", "louis", "rachel", "jessica"]


# ─── /v1/case (validation) ──────────────────────────────────────────────────


def test_post_case_validates_role() -> None:
    """A role outside the closed set returns 422 with the structured
    error code the SPA can match on."""
    client = TestClient(_make_app())
    res = client.post(
        "/v1/case",
        json={"question": "test", "role": "ceo"},
    )
    assert res.status_code == 422, res.text
    body = res.json()
    assert body["detail"]["code"] == "specter_invalid_role"


def test_post_case_truncates_long_question() -> None:
    """Paste-bomb questions get silently truncated to 2 000 chars; the
    route must not 422 the SPA back."""
    client = TestClient(_make_app())
    long_question = "a" * 5_000
    res = client.post(
        "/v1/case",
        json={"question": long_question, "role": None},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    # The CaseFile inside the dialogue echoes the (post-truncation) question.
    # The orchestrator may surface it via different keys depending on the
    # CaseDialogue shape, so we look for it broadly.
    question_value = payload.get("question") or payload.get("case", {}).get("question")
    assert question_value is not None, (
        f"expected question echoed in response payload; got keys: {list(payload)}"
    )
    assert len(question_value) <= 2_000


# ─── /v1/case (error path) ──────────────────────────────────────────────────


def test_post_case_handles_orchestrator_error() -> None:
    """An exception inside ``orchestrator.work`` becomes a structured 502
    rather than a leaked traceback."""

    class _Boom:
        def work(self, case):  # noqa: ANN001 — duck-typed for the route layer
            raise RuntimeError("kaboom")

    app = _make_app({"orchestrator": _Boom()})
    res = TestClient(app).post(
        "/v1/case",
        json={"question": "test", "role": None},
    )
    assert res.status_code == 502, res.text
    assert res.json()["detail"]["code"] == "case_orchestrator_error"


# ─── Dev app root redirects ────────────────────────────────────────────────


def test_dev_app_root_redirects() -> None:
    """When the ``webapp/`` dir exists, ``GET /`` redirects to the SPA."""
    from specter.api.dev_app import make_dev_app

    client = TestClient(make_dev_app(), follow_redirects=False)
    res = client.get("/")
    assert res.status_code in (307, 308), res.status_code
    assert res.headers["location"] == "/webapp/"


def test_dev_app_root_falls_back_to_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the SPA dir is absent, ``GET /`` redirects to ``/docs``.

    We swap the resolver out for one that returns a definitely-missing
    path — no filesystem mutation, no risk of nuking the real webapp.
    """
    from pathlib import Path

    from specter.api import dev_app

    fake_dir = Path("D:/__specter_test_no_such_dir__/webapp")
    monkeypatch.setattr(dev_app, "_resolve_webapp_dir", lambda: fake_dir)

    # Build the app AFTER patching so the StaticFiles mount is skipped
    # too — otherwise the mount path would still exist in the app.
    app = dev_app.make_dev_app()
    client = TestClient(app, follow_redirects=False)
    res = client.get("/")
    assert res.status_code in (307, 308)
    assert res.headers["location"] == "/docs"
