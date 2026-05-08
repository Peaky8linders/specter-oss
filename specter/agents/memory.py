"""Local-first JSON memory for the Mike Ross persona.

Inspired by mike-oss's local-only philosophy: nothing is uploaded,
nothing is shared between machines, the file lives under the user's
home directory and gets atomic writes so a crash mid-flush never
leaves a partial JSON object on disk.

Why a flat ``key → list[str]`` shape?
The orchestrator stores a small handful of facts per case
(``case:<case_id>`` → question + verdict + references) and the front
end occasionally asks "everything Mike remembers" via :meth:`all_keys`.
A nested document model would invite schema drift; a flat dict keeps
the file self-explanatory when a developer opens it in a text editor.

Concurrency
^^^^^^^^^^^
Writes go via a temp file + ``os.replace`` so a parallel reader either
sees the previous fully-formed JSON or the new fully-formed JSON —
never half a file. We don't take a process-level lock — Specter's
orchestrator is single-threaded per request and the memory file is
small enough that a last-writer-wins on concurrent ``remember`` calls
is the right tradeoff.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def _default_memory_path() -> Path:
    """Default path for the JSON memory file.

    ``~/.specter/mike_memory.json`` keeps the namespace tidy alongside
    any other per-user Specter state we add later (config, cached
    bridge probes, etc.). The directory is created lazily on first
    write — we never touch the filesystem at import time.
    """
    return Path.home() / ".specter" / "mike_memory.json"


class MikeMemory:
    """Local-first JSON memory — inspired by mike-oss's local-only philosophy.

    Default path: ``~/.specter/mike_memory.json``. Atomic writes via
    ``os.replace`` so a partial flush never corrupts the file.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path: Path = path if path is not None else _default_memory_path()
        # Lazy load — instantiating MikeMemory(path) shouldn't fail just
        # because the file isn't there yet (first run).
        self._store: dict[str, list[str]] = self._load()

    # ── Public API ────────────────────────────────────────────────────────

    def recall(self, key: str) -> list[str]:
        """Return the facts stored under ``key`` (empty list if unknown).

        The returned list is a fresh copy — callers can mutate it
        without polluting the in-memory store.
        """
        return list(self._store.get(key, []))

    def remember(self, key: str, fact: str) -> None:
        """Append a fact under ``key`` and atomically flush to disk.

        Duplicate facts are deduped — Mike doesn't say the same thing
        twice. We compare verbatim (whitespace-sensitive) to avoid
        accidentally collapsing two facts that differ only in
        punctuation; the orchestrator builds canonical fact strings so
        this rarely matters.
        """
        bucket = self._store.setdefault(key, [])
        if fact not in bucket:
            bucket.append(fact)
            self._flush()

    def all_keys(self) -> list[str]:
        """Return every key in the store, sorted for deterministic output."""
        return sorted(self._store.keys())

    # ── Internals ─────────────────────────────────────────────────────────

    def _load(self) -> dict[str, list[str]]:
        """Read the JSON file from disk, returning an empty store on miss.

        Tolerant of two soft failure modes that should not blow up the
        agent layer:

        * file missing — first run; return ``{}``.
        * file corrupted — stale partial write from an old version, or
          a developer hand-edit gone wrong. We log nothing (this is a
          library, not a service) and start over with ``{}``. The next
          ``remember`` call rewrites the file cleanly.
        """
        if not self._path.exists():
            return {}
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return {}
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        # Coerce values to ``list[str]`` — defensive against hand-edits
        # that nest a dict or a None under a key.
        out: dict[str, list[str]] = {}
        for k, v in data.items():
            if isinstance(k, str) and isinstance(v, list):
                out[k] = [str(item) for item in v]
        return out

    def _flush(self) -> None:
        """Atomically write the store to disk via temp file + rename."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # ``tempfile.NamedTemporaryFile`` in the same directory so the
        # rename below is on the same filesystem (the POSIX guarantee
        # for atomicity, and Windows ``os.replace`` cross-volume support
        # is not something we want to depend on).
        fd, tmp_path = tempfile.mkstemp(
            prefix=".mike_memory.",
            suffix=".tmp",
            dir=str(self._path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._store, f, indent=2, ensure_ascii=False, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._path)
        except OSError:
            # Best-effort cleanup of the temp file on any failure path —
            # we'd rather lose the new fact than leave litter behind.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
