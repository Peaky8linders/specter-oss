"""Specter Suits-themed agent overlay — case dialogue endpoint (FastAPI route).

Public surface for the comic-book agent layer. A compliance question is
reframed as a "case" worked by four characters loosely inspired by the
TV series *Suits* — Mike Ross, Rachel Zane, Louis Litt, Jessica Pearson —
and returned as an ordered :class:`CaseDialogue` of turns the front-end
renders one panel at a time.

Why this route exists:

* The Q&A endpoint (``POST /v1/eu-ai-act/ask``) is grounded but voiceless;
  it returns a single answer with citations and nothing else. Regulators
  and counsel often want to *see* the deliberation — what the associate
  recalled, where the adversary objected, how the partner ruled — and
  the comic-book SPA at ``/webapp/`` is designed to render exactly that.
* The dialogue is **deterministic by default**: every persona's claim
  is a pure function of the question + the data-pure catalogs in
  :mod:`specter.data`. The five-turn pipeline (Rachel → Mike → Louis →
  Rachel → Jessica) ships without paying for an LLM round trip on the
  hot path

Hallucination-reduction guard:

* Every external-facing reference inside a ``Turn.citations`` entry
  passes through :func:`specter.qa.models.reference_from_article_ref`
  before reaching the wire. The orchestrator already enforces this
  upstream — the route layer simply trusts the agent layer's contract,
  the same way the Q&A route trusts its retriever's filtered citations.
* A failure inside ``CaseOrchestrator.work`` is caught and converted to
  a clean ``502 case_orchestrator_error`` — never a leaked stack trace.

Tier resolution + rate limits mirror the Q&A route so a partner with a
valid ``X-Specter-Api-Key`` gets the privileged tier here too:

* **Privileged tier** — header validates against ``SPECTER_API_KEY`` env
  var. 60/min keyed on a sha256-truncated hash of the key.
* **Anonymous tier** — no header (or no configured key on this deploy).
  20/min keyed on a 16-hex sha256 hash of the client IP (raw IP is
  never persisted — GDPR Art. 4(5) pseudonymisation).

Header present-but-invalid returns 403 (silent downgrade would mask
consumer-side bugs). The two tiers live under different bucket prefixes
so a flood of anon traffic cannot exhaust a partner's privileged budget.

Module import is fail-soft: if the upstream :mod:`specter.agents` layer
is not yet built (or fails to import for any reason) this module still
imports cleanly. The router factory then returns a stub router whose
``POST /v1/case`` returns 503 ``case_layer_unavailable`` so callers get
a structured error instead of a 500. The 503 path is a deployment
indicator, not a normal route response — production should always have
the agents layer wired in.
"""

from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError
from slowapi import Limiter
from slowapi.util import get_remote_address

from specter.qa.auth import (
    optional_specter_api_key,
    validate_specter_api_key,
)

# ─── Fail-soft import of the agent layer ────────────────────────────────────
# The agents layer is owned by a separate module and may be absent at
# import time during integration. We import it inside a try/except so
# this route module always loads — a missing agents layer turns the
# /v1/case endpoint into a 503 rather than crashing FastAPI startup.
try:  # pragma: no cover — import guard exercised only when agents missing
    from specter.agents.case import (  # type: ignore[import-not-found]
        CaseDialogue,
        CaseFile,
        CaseOrchestrator,
        PersonaCustomisation,
    )
    from specter.agents.personas import (  # type: ignore[import-not-found]
        PERSONAS,
        Voice,
    )
    _AGENTS_AVAILABLE = True
    _AGENTS_IMPORT_ERROR: str | None = None
except Exception as exc:  # noqa: BLE001 — defensive guard
    CaseDialogue = None  # type: ignore[assignment, misc]
    CaseFile = None  # type: ignore[assignment, misc]
    CaseOrchestrator = None  # type: ignore[assignment, misc]
    PersonaCustomisation = None  # type: ignore[assignment, misc]
    PERSONAS = None  # type: ignore[assignment]
    Voice = None  # type: ignore[assignment, misc]
    _AGENTS_AVAILABLE = False
    _AGENTS_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


_log = logging.getLogger("specter.api.case_route")


# ─── Closed set of operator roles ───────────────────────────────────────────
# Mirrors :data:`specter.data.roles` but kept inline so this module is
# importable without the agents layer (which transitively re-exports the
# role data). The CaseFile contract treats role as advisory, not
# exhaustive — the deliberation pipeline picks up role-specific articles
# only when the role matches a known operator class. Anything else gets
# a structured 422 rather than silently re-running with role=None.
_VALID_ROLES: frozenset[str] = frozenset(
    {
        "provider",
        "deployer",
        "importer",
        "distributor",
        "authorised_representative",
        "product_manufacturer",
        "gpai_provider",
        "gpai_deployer",
        "notified_body",
    }
)


# ─── Wire shape: request body ───────────────────────────────────────────────


_VALID_VOICES: frozenset[str] = frozenset(
    {"harvey", "mike", "rachel", "louis", "jessica"}
)
_VALID_OVERRIDE_PROVIDERS: frozenset[str] = frozenset({"claude", "openai"})

# Per-persona system-prompt cap. The defaults in personas.py are ~400
# chars; user customisations can be longer (chain-of-thought, examples)
# but a 4 KiB cap keeps any single persona override well under most
# providers' system-prompt limits and prevents accidental paste-bombs.
_MAX_PERSONA_PROMPT = 4_000


class PersonaOverride(BaseModel):
    """One per-persona customisation for a single ``POST /v1/case`` call.

    The user picks a voice (``mike`` / ``rachel`` / ``louis`` /
    ``jessica``) and optionally:

    * overrides the system prompt (custom personality / style guide)
    * forces a specific LLM provider (``claude`` / ``openai``) — overrides the request's BYOK header for this voice
    * forces a specific model id

    When at least one override is present AND a BYOK key is available
    (either via headers or via a per-override ``api_key``), the
    orchestrator switches to LLM-backed claim generation for that
    voice. The deterministic citation-finding logic stays — only the
    *voice* of the claim text changes.
    """

    voice: str = Field(min_length=1)
    system_prompt: str | None = Field(default=None, max_length=_MAX_PERSONA_PROMPT)
    provider: str | None = Field(default=None)
    model: str | None = Field(default=None, max_length=128)
    api_key: str | None = Field(default=None, max_length=2048)


class CaseRequest(BaseModel):
    """``POST /v1/case`` request body.

    Mirrors the upstream :class:`specter.agents.case.CaseFile` minimally —
    only the fields the SPA can reasonably collect from a single text
    box, a role dropdown, and a "let Louis object" toggle. Everything
    else (case_id, prior turns, retrieval knobs) lives behind the
    orchestrator's defaults.

    ``question`` is internally truncated to 2 000 characters BEFORE the
    orchestrator runs — matching the Q&A route's per-question cap. We
    silently truncate (rather than 422) so the SPA's textarea can
    paste-bomb without an error round-trip.

    ``persona_overrides`` is the team-customisation surface — see
    :class:`PersonaOverride`. Empty / absent → fully deterministic
    rule-based dialogue (the v0.1.4 behaviour).
    """

    question: str = Field(min_length=1, max_length=10_000)
    role: str | None = Field(default=None)
    enable_louis_objection: bool = Field(default=True)
    persona_overrides: list[PersonaOverride] | None = Field(default=None)


# ─── Wire shape: persona catalog ────────────────────────────────────────────


class PersonaCard(BaseModel):
    """Front-end-friendly slice of :class:`specter.agents.personas.Persona`.

    The SPA bootstraps its panel palette + character roster from this
    list. We deliberately drop ``system_prompt`` — that string is
    LLM-mode plumbing, not UI copy, and serialising it would invite
    consumers to render it as character flavour text.
    """

    voice: str
    name: str
    title: str
    color: str
    accent_color: str
    catchphrase: str


# ─── Rate-limit plumbing (mirrors qa_route style; deliberately not shared) ──
# We re-implement the bucket helpers here rather than importing the
# private symbols from qa_route so the two endpoints can drift in tier
# limits independently (case is more expensive — 20/min anon vs 30/min
# anon for Q&A — because each call wakes four agents and writes to local
# memory, so the cheaper per-request budget keeps abuse manageable).

_RATE_KEY_PREFIX_AUTHED = "specter-case-key:"
_RATE_KEY_PREFIX_ANON = "specter-case-anon:"


def _hash16(value: str) -> str:
    """Truncated sha256 hex (16 chars / 64 bits) — pseudonymisation
    helper. Used for partner-key + IP under GDPR Art. 4(5)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _case_rate_key(request: Request) -> str:
    """Return the rate-limit bucket key for this request.

    Privileged tier: caller sent a valid ``X-Specter-Api-Key`` —
    bucket prefix ``specter-case-key:`` so 60/min applies.

    Anonymous tier: no header OR no configured key on this deploy —
    bucket prefix ``specter-case-anon:`` with a 16-hex IP hash so the
    20/min budget is per-source-IP rather than global.
    """
    api_key = request.headers.get("X-Specter-Api-Key", "")
    if api_key and validate_specter_api_key(api_key):
        return f"{_RATE_KEY_PREFIX_AUTHED}{_hash16(api_key)}"
    ip = get_remote_address(request) or "unknown"
    return f"{_RATE_KEY_PREFIX_ANON}{_hash16(ip)}"


def _case_dynamic_limit(key: str) -> str:
    """Map the rate-limit bucket key to its tier limit string."""
    if key.startswith(_RATE_KEY_PREFIX_AUTHED):
        return "60/minute"
    return "20/minute"


# ─── Persona-override resolution ────────────────────────────────────────────


def _resolve_persona_customisations(
    overrides: list[PersonaOverride] | None,
    request: Request,
) -> dict[Voice, PersonaCustomisation] | None:
    """Convert public ``PersonaOverride`` list → orchestrator customisations.

    The route layer is the single place where the BYOK header pair
    fans out into a per-persona key. Per-override ``provider`` /
    ``api_key`` always wins over the headers; that lets a power user
    run, say, Mike on Claude and Louis on ChatGPT in the same case
    without forcing every persona through one global provider.

    Returns ``None`` when no overrides are present so the orchestrator
    can short-circuit cleanly.

    Validates voices + providers loudly — anything unknown raises 422
    from the route. We do NOT pre-validate the API key shape (provider
    SDKs reject invalid keys with their own 4xx error, and any
    pre-validation here would just duplicate that work).
    """
    if not overrides:
        return None
    if not _AGENTS_AVAILABLE:
        return None

    # Read header BYOK once so we can fall through per-override.
    from specter.qa.byok import parse_byok_headers

    header_provider, header_key = parse_byok_headers(request)

    out: dict[Voice, PersonaCustomisation] = {}
    for ov in overrides:
        voice_str = (ov.voice or "").strip().lower()
        if voice_str not in _VALID_VOICES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "specter_invalid_voice",
                    "message": (
                        f"Unknown voice {ov.voice!r}. Expected one of: "
                        f"{sorted(_VALID_VOICES)}."
                    ),
                },
            )
        # Provider resolution: per-override wins, else header BYOK.
        provider_str = ov.provider
        if provider_str is not None:
            provider_str = provider_str.strip().lower()
            if provider_str and provider_str not in _VALID_OVERRIDE_PROVIDERS:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "specter_invalid_provider",
                        "message": (
                            f"Unknown provider {ov.provider!r}. Expected "
                            f"one of: {sorted(_VALID_OVERRIDE_PROVIDERS)}."
                        ),
                    },
                )
        else:
            provider_str = header_provider

        # Key resolution: per-override wins, else header BYOK.
        api_key = (ov.api_key or "").strip() or header_key

        # Coerce voice string → enum so the orchestrator's dict-keyed
        # lookup matches the Voice enum it stores in turn.speaker.
        voice_enum = Voice(voice_str)

        out[voice_enum] = PersonaCustomisation(
            system_prompt=(ov.system_prompt or None),
            provider=provider_str if provider_str else None,
            model=(ov.model or None),
            api_key=api_key if api_key else None,
        )
    return out or None


# ─── Router factory ─────────────────────────────────────────────────────────


def make_case_router(
    *,
    orchestrator: object | None = None,
    limiter: Limiter | None = None,
) -> APIRouter:
    """Build the Specter case-dialogue router.

    Args:
      orchestrator: optional pre-built ``CaseOrchestrator`` (or any
        object exposing a ``work(case) -> CaseDialogue`` method).
        Tests inject a stub here to exercise the error path without
        spinning up the real deliberation pipeline. Production callers
        leave this ``None`` and let the route construct a default
        orchestrator on the fly — cheap, in-memory, and deterministic.
      limiter: optional ``slowapi.Limiter``. If omitted, a fresh
        IP-keyed limiter is created — works out of the box but does not
        share state with the host's other rate-limited routes.

    Returns:
      A ``fastapi.APIRouter`` with two endpoints:

      * ``POST /v1/case`` — runs the deliberation pipeline.
      * ``GET /v1/case/personas`` — bootstraps the SPA's character roster.

      When the agent layer fails to import at module load time the
      router still mounts but its handlers all return ``503`` with
      ``code=case_layer_unavailable`` — a deployment indicator, not a
      normal response.
    """
    if limiter is None:
        limiter = Limiter(key_func=get_remote_address)

    router = APIRouter(tags=["specter-case"])

    # Fail-soft fallback: agent layer not importable. We still register
    # the routes so the FastAPI app object stays uniform across deploys —
    # the SPA gets a structured 503 instead of an HTML 404 from a missing
    # path, which is far easier to debug from devtools.
    if not _AGENTS_AVAILABLE:
        @router.post("/v1/case")
        def _case_unavailable() -> None:
            _log.warning(
                "case route invoked but specter.agents is unavailable: %s",
                _AGENTS_IMPORT_ERROR,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "case_layer_unavailable",
                    "message": (
                        "The Specter agent layer is not available on this "
                        "deployment. Ensure specter.agents is installed."
                    ),
                },
            )

        @router.get("/v1/case/personas")
        def _personas_unavailable() -> None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "case_layer_unavailable",
                    "message": (
                        "The Specter agent layer is not available on this "
                        "deployment. Ensure specter.agents is installed."
                    ),
                },
            )

        return router

    # Resolve the orchestrator lazily-but-eagerly: build one now so the
    # default in-memory store warms before the first request. Tests can
    # still inject a stub via the kwarg — including objects that aren't
    # subclasses of CaseOrchestrator, hence the duck-typed signature.
    if orchestrator is None:
        orchestrator = CaseOrchestrator()  # type: ignore[misc]

    @router.get("/v1/case/personas", response_model=list[PersonaCard])
    def list_personas() -> list[PersonaCard]:
        """Persona catalog for the SPA bootstrap.

        Returns one card per character. The SPA caches this on first
        load and re-uses it for every subsequent ``/v1/case`` call —
        the catalog is process-static so a CDN can cache it freely.
        """
        return [
            PersonaCard(
                voice=str(p.voice),
                name=p.name,
                title=p.title,
                color=p.color,
                accent_color=p.accent_color,
                catchphrase=p.catchphrase,
            )
            for p in PERSONAS.values()
        ]

    @router.post(
        "/v1/case",
        responses={
            422: {"description": "Invalid role or malformed body"},
            502: {"description": "Orchestrator pipeline error"},
            503: {"description": "Agent layer unavailable on this deploy"},
        },
    )
    @limiter.limit(_case_dynamic_limit, key_func=_case_rate_key)
    def post_case(
        request: Request,
        body: CaseRequest,
        api_key: str | None = Depends(optional_specter_api_key),
    ) -> object:
        """Run the deliberation pipeline and return a CaseDialogue.

        Pipeline (deterministic):
          1. Rachel frames the question.
          2. Mike recalls articles.
          3. Louis objects (or concedes) — gated by
             ``enable_louis_objection``.
          4. Rachel mediates.
          5. Jessica rules.
        """

        # Role validation — closed set, anything else is a 422.
        # We accept None freely (the orchestrator handles unknown roles
        # by reading nothing from the role-obligations index) but reject
        # garbage-string roles loudly so a typo on the SPA's dropdown
        # surfaces at the boundary instead of leaking into the dialogue.
        if body.role is not None and body.role not in _VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "specter_invalid_role",
                    "message": (
                        f"Unknown role {body.role!r}. Expected one of: "
                        f"{sorted(_VALID_ROLES)}, or null."
                    ),
                },
            )

        # Per-question cap mirrors the Q&A route. Truncation is silent —
        # paste-bombs from the SPA textarea must not 422.
        question = body.question[:2_000]

        # Persona overrides → orchestrator customisations. Validation
        # rejects unknown voices / unknown providers loudly; missing
        # fields fall through to the BYOK header path so a user who
        # configured "use Claude for everyone" via the global
        # X-Specter-LLM-* headers + a per-voice system_prompt only
        # gets the LLM voice without re-pasting their key into every
        # override.
        persona_customisations = _resolve_persona_customisations(
            body.persona_overrides, request
        )

        try:
            case = CaseFile(  # type: ignore[misc]
                question=question,
                role=body.role,
                enable_louis_objection=body.enable_louis_objection,
                persona_customisations=persona_customisations,
            )
        except ValidationError as exc:
            # The agent layer's own model rejected something we passed
            # through — return the structured shape so the SPA can
            # render a useful error rather than a generic 500.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "specter_invalid_case",
                    "message": "CaseFile validation failed.",
                    "errors": exc.errors()[:5],
                },
            ) from exc

        # Parse BYOK headers if the caller sent them. The deterministic
        # orchestrator does not currently consume an LLM, but we observe
        # the headers so a future LLM-backed mode can pick them up
        # without changing the wire contract. The key itself is never
        # logged — only a hash of its bucket so we can reason about
        # tenant traffic in metrics without leaking material.
        from specter.qa.byok import parse_byok_headers

        byok_provider, byok_key = parse_byok_headers(request)
        if byok_provider and byok_key:
            _log.info(
                "case.byok_observed provider=%s key_hash=%s",
                byok_provider, _hash16(byok_key),
            )

        try:
            dialogue = orchestrator.work(case)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 — convert to structured 502
            # Never leak the traceback. The orchestrator runs entirely
            # in-process so a raise here is either (a) a real bug we want
            # to fix, or (b) a network blip — both classify
            # as "upstream pipeline failed" from the SPA's point of view.
            _log.warning("case orchestrator error: %s: %s", type(exc).__name__, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "case_orchestrator_error",
                    "message": (
                        "The agent deliberation pipeline failed. "
                        "Try again in a moment."
                    ),
                },
            ) from exc

        return dialogue

    return router


# Convenience: pre-built router with the default orchestrator + limiter.
# Hosts that want to inject a custom orchestrator should call
# :func:`make_case_router` themselves rather than import this object.
case_router = make_case_router()


__all__ = [
    "CaseRequest",
    "PersonaCard",
    "case_router",
    "make_case_router",
]
