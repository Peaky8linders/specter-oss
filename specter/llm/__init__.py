"""LLM-provider helpers for Specter.

Currently ships one provider — :mod:`specter.llm.mistral_provider` — for
Mistral La Plateforme. Hosts that want a different provider plug in via
the pluggable retriever protocol on :mod:`specter.api.qa_route`; this
package is the reference implementation for the Mistral path so users
can ship a working Q&A endpoint with one env var (``MISTRAL_API_KEY``).
"""

from specter.llm.mistral_provider import (
    MistralProvider,
    MistralRequest,
    MistralResponse,
    get_mistral_provider,
    is_mistral_enabled,
    reset_mistral_provider,
    resolve_provider,
)

__all__ = [
    "MistralProvider",
    "MistralRequest",
    "MistralResponse",
    "get_mistral_provider",
    "is_mistral_enabled",
    "reset_mistral_provider",
    "resolve_provider",
]
