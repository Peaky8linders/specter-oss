# Contributing to Specter

Thanks for your interest in Specter. This is a small, opinionated package — the bar for new public surface is high, the bar for fixes + tests + docs is low.

## What we welcome

- **Bug fixes** in the data catalogs (articles missing, wrong refs, taxonomy errors)
- **New crosswalk entries** for MITRE ATLAS / OWASP AI Exchange / NIST AI RMF
- **Test coverage** — every check in `ComplianceRewardHackDetector` should have a positive + negative case
- **Documentation** — examples that show the package solving a real problem
- **Vendored standard refreshes** — when OWASP APTS / MITRE ATLAS / OWASP AI Exchange ship a new version, a PR that bumps the snapshot + the version pin is always welcome

## What we'll usually decline

- New top-level modules — Specter is intentionally narrow; if it doesn't fit `data` / `judge` / `qa` / `api` / `apts` / `ontology`, it probably belongs in a downstream package
- Wrappers around proprietary LLM providers — the `qa.api` retriever protocol is pluggable on purpose; ship your provider as a separate package
- Heavy runtime dependencies — every dep added to the `core` install is a tax on every user; keep the dependency graph tight

## Setup

```bash
git clone https://github.com/Peaky8linders/specter-oss
cd specter-oss
pip install -e '.[dev,api]'
pytest
ruff check .
```

## Quality gate

A PR is mergeable when:

1. `pytest` passes locally (the smoke suite under `tests/` runs in seconds)
2. `ruff check .` is clean
3. `python -c "import specter; from specter.apts import assess_self; assess_self()"` exits 0
4. Any new public symbol has at least one test + a docstring

## Provenance discipline

Specter inherits a strict provenance posture from the upstream:

- **Never silence exceptions with bare `except: pass`** — silent swallowing destroys the signal antifragile systems need. Use `logger.debug("event_name field=%s error=%s", field, exc)` at minimum, even for best-effort fallbacks.
- **Every `# nosec` must record its reasoning inline** — future reviewers should see what was considered, not just that it was silenced.
- **Vendored data carries its license + source URL** — see the top of `specter/data/atlas.py` etc. for the pattern.

## License

By submitting a PR you agree your contribution is licensed under the [MIT License](LICENSE) of this repository.
