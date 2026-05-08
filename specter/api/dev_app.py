"""Specter — dev-only FastAPI app composing the Q&A and case routes.

This is dev-only — production hosts wire their own router composition
(usually behind their gateway, with their own auth, their own retriever,
and their own SPA mount point). The app here exists to give a developer
a single ``uvicorn`` entry point that spins up:

* ``POST /v1/eu-ai-act/ask``  — grounded Q&A endpoint.
* ``POST /v1/case``           — Suits-themed agent dialogue.
* ``GET  /v1/case/personas``  — SPA bootstrap.
* ``GET  /webapp/...``        — comic-book SPA static mount, when present.
* ``GET  /``                  — redirect to the SPA, falling back to /docs.

Run with::

    uvicorn specter.api.dev_app:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from specter.api.case_route import make_case_router
from specter.api.qa_route import qa_router


def _resolve_webapp_dir() -> Path:
    """Locate the comic-book SPA directory next to the package.

    Pulled out as a helper so tests can monkeypatch the resolver and
    exercise the "webapp missing" fallback without touching the disk.
    """
    return Path(__file__).resolve().parent.parent.parent / "webapp"


def make_dev_app() -> FastAPI:
    """Build the dev-only FastAPI app.

    Re-builds the router stack on every call so tests can spin up a
    fresh app per test without polluting the default ``app`` instance
    at module level.
    """
    app = FastAPI(
        title="Specter — dev app",
        description="Q&A endpoint + Suits-themed agent layer + comic-book SPA.",
    )
    app.include_router(qa_router)
    app.include_router(make_case_router())

    webapp_dir = _resolve_webapp_dir()
    if webapp_dir.exists():
        app.mount(
            "/webapp",
            StaticFiles(directory=str(webapp_dir), html=True),
            name="webapp",
        )

    @app.get("/", include_in_schema=False)
    def _root() -> RedirectResponse:
        # Redirect to the SPA when present, else to /docs. Resolved on
        # every request so an `--reload` developer dropping the webapp
        # directory in mid-session immediately sees the SPA without
        # restarting uvicorn.
        if _resolve_webapp_dir().exists():
            return RedirectResponse(url="/webapp/")
        return RedirectResponse(url="/docs")

    return app


# Module-level app for the canonical ``uvicorn specter.api.dev_app:app``
# invocation. Tests prefer ``make_dev_app()`` for isolation.
app = make_dev_app()


__all__ = ["app", "make_dev_app"]
