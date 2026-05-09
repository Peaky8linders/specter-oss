"""Suits-themed multi-agent overlay for Specter.

A small, deterministic overlay that reframes a compliance question as a
"case" worked by four characters loosely inspired by the TV series *Suits*
and the local-first OSS fork of Will Chen's ``mike`` legal AI platform
([mikeOnBreeze/mike-oss](https://github.com/mikeOnBreeze/mike-oss)).

The layer is intentionally rule-based — every persona's behaviour is a
pure function of the question + the data-pure catalogs in
:mod:`specter.data` — so the FastAPI route + the comic-book front-end
can render a fully predictable dialogue without paying for an LLM round
trip on the hot path. An optional :class:`MikeOSSBridge` adapter lets a
locally-running mike-oss instance enrich Mike's recall, but the agent
layer never depends on it.

Public surface:

* :class:`Voice`, :class:`Persona`, :data:`PERSONAS` — character catalog.
* :class:`MikeMemory` — local-first JSON memory (atomic writes).
* :class:`MikeOSSBridge` — optional HTTP adapter to mike-oss; falls
  through silently on any error.
* :class:`Citation`, :class:`Turn`, :class:`CaseFile`,
  :class:`CaseDialogue` — the wire shape consumed by the route layer
  and the comic-book front-end.
* :class:`CaseOrchestrator` — the deterministic pipeline that produces
  a five-turn dialogue (Rachel → Mike → Louis → Rachel → Jessica).
"""

from __future__ import annotations

from specter.agents.case import (
    CaseDialogue,
    CaseFile,
    CaseOrchestrator,
    Citation,
    PersonaCustomisation,
    Turn,
)
from specter.agents.memory import MikeMemory
from specter.agents.mike_bridge import MikeOSSBridge
from specter.agents.personas import PERSONAS, Persona, Voice

__all__ = [
    "PERSONAS",
    "CaseDialogue",
    "CaseFile",
    "CaseOrchestrator",
    "Citation",
    "MikeMemory",
    "MikeOSSBridge",
    "Persona",
    "PersonaCustomisation",
    "Turn",
    "Voice",
]
