"""LLM-provider helpers for Specter.

Three providers ship in-tree, all sharing the same fail-soft contract
(``complete()`` never raises; failures land in ``Response.error``):

* :mod:`specter.llm.mistral_provider` — Mistral La Plateforme
  (``MISTRAL_API_KEY``).
* :mod:`specter.llm.claude_provider` — Anthropic Claude
  (``ANTHROPIC_API_KEY``).
* :mod:`specter.llm.openai_provider` — OpenAI ChatGPT
  (``OPENAI_API_KEY``).

Hosts that want a different provider plug in via the pluggable retriever
protocol on :mod:`specter.api.qa_route`. These three are the reference
implementations so users can ship a working Q&A endpoint with one env
var (or one ``api_key=`` parameter for BYOK / multi-tenant deploys).

The module-level imports are intentionally side-effect-free: each
provider lazy-loads its SDK on the first ``complete()`` call, so
``import specter.llm`` works on a deploy that has only one of the
three SDKs installed.
"""

from specter.llm.claude_provider import (
    ClaudeProvider,
    ClaudeRequest,
    ClaudeResponse,
    get_claude_provider,
    is_claude_enabled,
    reset_claude_provider,
)
from specter.llm.mistral_provider import (
    MistralProvider,
    MistralRequest,
    MistralResponse,
    get_mistral_provider,
    is_mistral_enabled,
    reset_mistral_provider,
    resolve_provider,
)
from specter.llm.openai_provider import (
    OpenAIProvider,
    OpenAIRequest,
    OpenAIResponse,
    get_openai_provider,
    is_openai_enabled,
    reset_openai_provider,
)

__all__ = [
    # Mistral
    "MistralProvider",
    "MistralRequest",
    "MistralResponse",
    "get_mistral_provider",
    "is_mistral_enabled",
    "reset_mistral_provider",
    "resolve_provider",
    # Claude
    "ClaudeProvider",
    "ClaudeRequest",
    "ClaudeResponse",
    "get_claude_provider",
    "is_claude_enabled",
    "reset_claude_provider",
    # OpenAI
    "OpenAIProvider",
    "OpenAIRequest",
    "OpenAIResponse",
    "get_openai_provider",
    "is_openai_enabled",
    "reset_openai_provider",
]
