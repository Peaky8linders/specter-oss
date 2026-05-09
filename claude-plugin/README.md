# Specter — Claude Code plugin

EU AI Act compliance toolkit for Claude Code. Wraps the `specter`
Python package as a local stdio MCP server + slash-command set.

**No hosted backend required.** The MCP server runs locally, in your
Claude Code session, against the canonical EU AI Act article catalog
+ agentic taxonomy + role-obligation registry shipped in the
`specter` Python package.

## Install

```bash
# 1. Install the Python package + plugin extra
pip install 'specter[plugin]>=0.1.2'

# 2. Install the plugin into Claude Code
claude plugins install ./claude-plugin
# or, from the repository root:
# claude plugins install github:Peaky8linders/specter-oss/claude-plugin
```

After install, restart Claude Code to load the plugin. Verify with:

```
/specter:list-articles kind="annexes"
```

You should see a JSON list of the 13 EU AI Act annexes.

## Slash commands

| Command | What it does |
|---|---|
| [`/specter:check-article`](commands/check-article.md) | Validate a citation against the canonical 113-article + 13-annex catalog |
| [`/specter:format-citation`](commands/format-citation.md) | Convert internal `Art. X(Y)(Z)` into publication `Article X.Y.Z` |
| [`/specter:list-articles`](commands/list-articles.md) | Return the full EU AI Act surface (113 articles + 13 annexes) |
| [`/specter:taxonomy`](commands/taxonomy.md) | Four-axis agentic-AI compound-risk taxonomy (cascading / emergent / attribution / temporal) |
| [`/specter:role-obligations`](commands/role-obligations.md) | List EU AI Act articles applicable to a given operator role |
| [`/specter:judge-proposal`](commands/judge-proposal.md) | Run a roadmap-task proposal through the LLM-as-Judge reward-hack detector |

## MCP tools

The same surface is exposed as 6 MCP tools so any LLM agent in your
Claude Code session can call them programmatically:

```
specter_check_article          specter_get_taxonomy
specter_format_citation        specter_role_obligations
specter_list_articles          specter_judge_proposal
```

See `.mcp.json` for the full input-schema definitions.

## How it works

```
Claude Code session
     │
     ▼
  /specter:check-article ref="Art. 13(1)(a)"
     │
     ▼
  MCP stdio server (python -m specter.mcp_server)
     │
     ▼
  specter.data.articles_existence.ARTICLE_EXISTENCE
     │
     ▼
  { "valid": true, "resolved": "Art. 13", ... }
```

The plugin manifest (`plugin.json`) declares the slash commands.
The `.mcp.json` file declares the local stdio server. The Python
side (`python -m specter.mcp_server`) imports the relevant module
and returns the JSON.

## Troubleshooting

**`/specter:*` commands don't autocomplete.** Restart Claude Code
after `claude plugins install`. Plugins are loaded at session start.

**MCP server fails to start.** Check that `specter` is on the same
Python interpreter Claude Code is invoking. From a terminal:

```bash
python -c "import specter; print(specter.__version__)"
python -m specter.mcp_server  # should hang on stdin (waiting for MCP frames)
```

If `python` resolves to a different interpreter than the one Claude
Code uses, edit `.mcp.json` and pin the absolute path:

```json
{
  "mcpServers": {
    "specter": {
      "command": "/path/to/your/python",
      "args": ["-m", "specter.mcp_server"]
    }
  }
}
```

**`mcp` package missing.** The plugin requires the `mcp` Python SDK,
which is pulled in by the `[plugin]` extra:

```bash
pip install 'specter[plugin]>=0.1.2'
```

## Beyond the plugin: the Suits-themed comic SPA

`specter` v0.1.6 ships a five-voice agent overlay (Harvey / Mike /
Rachel / Louis / Jessica) and a two-pane Casebook SPA. The settings
drawer has a **Provider** tab for bringing your own Anthropic Claude /
OpenAI ChatGPT / Mistral key, and a **Team** tab for customising each
character independently — pick the model per persona, rewrite the
system prompt, mix-and-match providers across the team. Mike's article
recall is enriched (default-on) by an optional adapter to a locally-
running Will Chen `mike` legal AI fork
([willchen96/mike](https://github.com/willchen96/mike) /
[mikeOnBreeze/mike-oss](https://github.com/mikeOnBreeze/mike-oss)) on
`http://127.0.0.1:3000`; fail-soft if nothing is listening.

The Claude Code plugin is unaffected — slash commands and MCP tools
work the same. The agent layer is an *extra* surface: install with
`pip install -e '.[api]'` and run `uvicorn specter.api.dev_app:app
--reload`. See the [root README](../README.md#3-casebook-spa--suits-themed-agent-overlay)
for the character roster, the team-customisation flow, and BYOK details.

## License

MIT (matching the `specter` package). See [LICENSE](../LICENSE) at
the repo root.
