"""Optional adapter to a locally-running mike-oss instance.

If a developer has Will Chen's mike-oss running on ``localhost:3000``
(or anywhere else, configured via ``MIKE_OSS_BASE_URL``), this adapter
forwards Mike Ross's recall query to its document-search endpoint and
splices the results into Mike's article-recall pass.

The bridge is **optional** — every failure path returns an empty
result so the agent layer keeps working without it:

* mike-oss not installed, port not listening → ``is_available()`` False
* mike-oss running but ``/health`` returns non-2xx → False
* mike-oss returns malformed JSON / wrong shape → ``search`` returns ``[]``
* network partition mid-search → ``search`` returns ``[]``

We use ``urllib.request`` from the standard library on purpose — adding
a third-party HTTP client (``httpx``, ``requests``) for a feature that's
*optional* would balloon the install footprint of a compliance toolkit.

Probe caching
^^^^^^^^^^^^^
``is_available()`` is called every time the orchestrator runs Mike's
recall. Probing the network on each call would add ~5-50 ms of latency
to every case. We cache the result for 30 seconds — long enough that a
typical interactive session re-uses the probe, short enough that the
user can ``docker-compose up mike-oss`` and have it picked up without
restarting Specter.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

# Cache TTL for the ``/health`` probe. Tuned so an interactive UI loop
# (one case every few seconds) re-uses the probe without thrashing the
# port, while a longer-running service still picks up a freshly-started
# mike-oss within a reasonable window.
_PROBE_TTL_SECONDS = 30.0


class MikeOSSBridge:
    """HTTP adapter to a local mike-oss instance.

    Wire shape (best-effort guesses; we accept anything that responds
    sensibly to the probe + search endpoints):

    * ``GET /health`` — any 2xx response means "available".
    * ``POST /api/search`` with ``{"query": "..."}`` — expects a JSON
      list of objects with a ``"text"`` field. Anything else → ``[]``.

    The bridge never raises — every error becomes either ``False``
    (probe) or ``[]`` (search) so the orchestrator can wire it in
    without ``try/except`` boilerplate at every call site.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 2.0,
    ) -> None:
        # Resolution precedence: explicit kwarg → ``MIKE_OSS_BASE_URL``
        # env var → built-in default. This mirrors how Specter's other
        # optional integrations resolve credentials (see
        # ``specter/llm/mistral.py::MistralProvider``).
        if base_url is None:
            base_url = os.environ.get("MIKE_OSS_BASE_URL", "http://localhost:3000")
        # Normalize: strip a trailing slash so endpoint joins are clean.
        self._base_url: str = base_url.rstrip("/")
        self._timeout: float = timeout

        # ``_cached_available`` is None until the first probe. After
        # that it stores ``(is_up, monotonic_timestamp)`` so we can
        # refresh after the TTL expires without holding a lock.
        self._cached_available: tuple[bool, float] | None = None

    # ── Probe ─────────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Return True iff a recent probe confirmed mike-oss is up.

        Cached for :data:`_PROBE_TTL_SECONDS` seconds. Errors are
        always swallowed — a network blip translates to "not available"
        for this case, not an exception that bubbles up to the user.
        """
        now = time.monotonic()
        cached = self._cached_available
        if cached is not None and (now - cached[1]) < _PROBE_TTL_SECONDS:
            return cached[0]
        result = self._probe()
        self._cached_available = (result, now)
        return result

    def _probe(self) -> bool:
        url = f"{self._base_url}/health"
        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as resp:
                # ``status`` is the canonical attribute on http.client
                # responses; ``getcode()`` is the legacy fallback.
                status = getattr(resp, "status", None) or resp.getcode()
                return 200 <= int(status) < 300
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return False
        except Exception:  # noqa: BLE001 — adapter contract: never raise
            return False

    # ── Search ────────────────────────────────────────────────────────────

    def search(self, query: str) -> list[str]:
        """Forward ``query`` to mike-oss; return list of text snippets.

        Returns an empty list on any failure — the orchestrator treats
        an empty bridge response identically to "bridge not configured",
        so no caller needs to special-case the error path.
        """
        if not query or not query.strip():
            return []
        url = f"{self._base_url}/api/search"
        body = json.dumps({"query": query}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read()
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return []
        except Exception:  # noqa: BLE001 — adapter contract: never raise
            return []

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []

        if not isinstance(decoded, list):
            return []

        out: list[str] = []
        for item in decoded:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    out.append(text.strip())
        return out
