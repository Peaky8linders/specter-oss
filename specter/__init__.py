"""Specter — EU AI Act compliance toolkit.

Provides:

* :mod:`specter.data` — canonical EU AI Act article catalog (113 articles
  + 13 annexes), agentic-AI compound-risk taxonomy, 9-role obligation
  registry, rationalization (rebutted-excuse) registry, ontology mapping.
* :mod:`specter.judge` — LLM-as-Judge for compliance roadmap
  proposals + three-agent (Finder / Adversary / Referee) adversarial
  verifier.
* :mod:`specter.qa` — grounded EU AI Act Q&A with closed-world
  refusal + reference validation against the article catalog.
* :mod:`specter.api` — minimal FastAPI router exposing the Q&A
  endpoint with a pluggable retriever.
* :mod:`specter.ontology` — RDF/Turtle OWL ontology aligning the
  EU AI Act with AIRO + DPV.

The package is data-pure where it can be: every taxonomy / catalog /
ontology layer is deterministic for the same inputs, no I/O, no
mutable state.
"""

__version__ = "0.1.6"
