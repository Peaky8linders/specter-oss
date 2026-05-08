"""Specter MCP server — stdio transport for Claude Code + other MCP clients.

Exposes the load-bearing read surfaces of the Specter package as MCP
tools so an LLM agent can validate citations, query the agentic-AI
taxonomy, look up role obligations, run the reward-hack judge, and
fetch APTS conformance scorecards without writing Python.

Run directly:

    python -m specter.mcp_server

Or wire into a Claude Code plugin via ``.mcp.json``:

    {
      "mcpServers": {
        "specter": {
          "command": "python",
          "args": ["-m", "specter.mcp_server"]
        }
      }
    }

Install the optional plugin extra to pull the MCP SDK:

    pip install 'specter[plugin]'
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("specter")


# ─── Tool schemas ──────────────────────────────────────────────────────────


_TOOLS: list[Tool] = [
    Tool(
        name="specter_check_article",
        description=(
            "Validate an EU AI Act article reference against the canonical 113-article "
            "+ 13-annex catalog. Accepts internal form (`Art. 13(1)(a)`, `Annex IV(2)`) "
            "with prefix-fallback semantics. Returns boolean + canonical resolved form."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ref": {
                    "type": "string",
                    "description": "Citation to validate, e.g. 'Art. 13(1)(a)' or 'Annex IV'.",
                },
            },
            "required": ["ref"],
        },
    ),
    Tool(
        name="specter_format_citation",
        description=(
            "Convert internal-form `Art. X(Y)(Z)` / `Annex IV(N)` references into "
            "publication form `Article X.Y.Z` / `Annex IV.N`. Returns null when the "
            "reference is hallucinated or malformed (does not exist in the catalog)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ref": {"type": "string", "description": "Internal-form reference."},
            },
            "required": ["ref"],
        },
    ),
    Tool(
        name="specter_list_articles",
        description=(
            "Return the canonical EU AI Act surface — 113 articles + 13 annexes from "
            "Regulation (EU) 2024/1689. Use to ground LLM output against an authoritative "
            "list before citing."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["all", "articles", "annexes"],
                    "default": "all",
                },
            },
        },
    ),
    Tool(
        name="specter_apts_self_conformance",
        description=(
            "Return the OWASP APTS v0.1.0 self-conformance scorecard for the reference "
            "platform — headline %, tier achievement (Foundation / Verified / Comprehensive), "
            "per-domain breakdown across the 8 conformance domains, and counts. "
            "Frozen baseline at ~73.5%."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="specter_apts_requirement",
        description=(
            "Look up a single OWASP APTS requirement by id (e.g. APTS-SE-001). "
            "Returns the full requirement record including domain, tier, classification "
            "(MUST/SHOULD), title, and statement text."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "requirement_id": {
                    "type": "string",
                    "description": "APTS requirement id, e.g. 'APTS-SE-001'.",
                },
            },
            "required": ["requirement_id"],
        },
    ),
    Tool(
        name="specter_get_taxonomy",
        description=(
            "Return the four-axis agentic-AI compound-risk taxonomy (cascading / "
            "emergent / attribution / temporal) grounded in *AI Agents Under EU Law* "
            "(working paper, 7 April 2026, §10.4). Each axis is anchored to specific "
            "EU AI Act articles + KB dimensions + threat-category cross-walks."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="specter_role_obligations",
        description=(
            "Return EU AI Act articles that apply to a given operator role. Roles: "
            "provider | deployer | importer | distributor | product_manufacturer | "
            "authorized_representative | gpai_provider | gpai_systemic_provider | "
            "extraterritorial_non_eu. Returns primary + secondary article references."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "description": (
                        "Operator role slug. One of: provider | deployer | importer | "
                        "distributor | product_manufacturer | authorized_representative | "
                        "gpai_provider | gpai_systemic_provider | extraterritorial_non_eu."
                    ),
                },
            },
            "required": ["role"],
        },
    ),
    Tool(
        name="specter_judge_proposal",
        description=(
            "Run a roadmap-task proposal through the ComplianceRewardHackDetector "
            "(LLM-as-Judge). Six checks: plagiarism + origin, KB reality, coverage "
            "plausibility, effort sanity, contract completeness, rebutted-excuse match. "
            "Returns blocked + reasons + origin. Pass the proposal as a JSON object "
            "matching the RawProposal shape."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "proposal": {
                    "type": "object",
                    "description": (
                        "Raw proposal in the RawProposal shape. Required keys: "
                        "task_id, task_title, description, agent, priority, "
                        "effort_hours, dimension_id, prompt, acceptance_criteria, "
                        "output_files, article_paragraphs, contract_verification."
                    ),
                },
                "valid_dimensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Dimension IDs the host KB recognises. The detector blocks any "
                        "proposal whose dimension_id is not in this set."
                    ),
                },
            },
            "required": ["proposal", "valid_dimensions"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return _TOOLS


# ─── Tool dispatch ─────────────────────────────────────────────────────────


def _wrap(payload: Any) -> list[TextContent]:
    """Shape every tool response as a single TextContent with JSON body."""
    return [TextContent(type="text", text=json.dumps(payload, default=str, indent=2))]


def _check_article(ref: str) -> dict[str, Any]:
    from specter.data.articles_existence import ARTICLE_EXISTENCE

    raw = (ref or "").strip()
    if not raw:
        return {"valid": False, "reason": "empty reference"}

    if raw in ARTICLE_EXISTENCE:
        return {"valid": True, "resolved": raw, "exact_match": True}

    candidate = raw
    while "(" in candidate:
        candidate = candidate.rsplit("(", 1)[0].strip()
        if candidate in ARTICLE_EXISTENCE:
            return {
                "valid": True,
                "resolved": candidate,
                "exact_match": False,
                "note": "matched via prefix-fallback (sub-paragraph inheritance)",
            }
    return {
        "valid": False,
        "reason": "reference does not exist in the EU AI Act catalog",
    }


def _format_citation(ref: str) -> dict[str, Any]:
    from specter.qa.models import reference_from_article_ref

    formatted = reference_from_article_ref(ref or "")
    if formatted is None:
        return {"input": ref, "formatted": None, "valid": False}
    return {"input": ref, "formatted": formatted, "valid": True}


def _list_articles(kind: str = "all") -> dict[str, Any]:
    from specter.data.articles_existence import ARTICLE_EXISTENCE

    articles = sorted(r for r in ARTICLE_EXISTENCE if r.startswith("Art. "))
    annexes = sorted(r for r in ARTICLE_EXISTENCE if r.startswith("Annex "))
    if kind == "articles":
        return {"count": len(articles), "items": articles}
    if kind == "annexes":
        return {"count": len(annexes), "items": annexes}
    return {
        "articles": {"count": len(articles), "items": articles},
        "annexes": {"count": len(annexes), "items": annexes},
        "total": len(ARTICLE_EXISTENCE),
    }


def _apts_self_conformance() -> dict[str, Any]:
    from specter.apts import assess_self

    report = assess_self()
    return {
        "apts_version": report.apts_version,
        "headline_score": round(report.headline_score, 3),
        "headline_tier": report.headline_tier.value if report.headline_tier else None,
        "counts": report.counts,
        "tier_status": [
            {
                "tier": t.tier.value,
                "label": t.label,
                "achieved": t.achieved,
                "must_satisfied": t.must_satisfied,
                "must_total": t.must_total,
                "coverage_score": round(t.coverage_score, 3),
            }
            for t in report.tier_status
        ],
        "domain_summaries": [
            {
                "domain": d.domain.value,
                "total": d.total,
                "satisfied": d.satisfied,
                "partial": d.partial,
                "gap": d.gap,
                "coverage_score": round(d.coverage_score, 3),
            }
            for d in report.domain_summaries
        ],
    }


def _apts_requirement(requirement_id: str) -> dict[str, Any]:
    from specter.apts.requirements import requirement_by_id

    req = requirement_by_id(requirement_id)
    if req is None:
        return {"found": False, "requirement_id": requirement_id}
    payload = req.model_dump(mode="json")
    payload["found"] = True
    return payload


def _get_taxonomy() -> dict[str, Any]:
    from specter.data.taxonomy import (
        AGENT_ARCHETYPES,
        COMPOUND_RISK_TYPES,
        TAXONOMY_VERSION,
        THREAT_CATEGORIES,
        AgentArchetype,
        CompoundRiskType,
        ThreatCategory,
    )

    return {
        "version": TAXONOMY_VERSION,
        "compound_risk_types": [t.value for t in CompoundRiskType],
        "threat_category_ids": [t.value for t in ThreatCategory],
        "agent_archetype_ids": [a.value for a in AgentArchetype],
        "compound_risks": list(COMPOUND_RISK_TYPES),
        "threat_categories": list(THREAT_CATEGORIES),
        "agent_archetypes": list(AGENT_ARCHETYPES),
    }


def _role_obligations(role: str) -> dict[str, Any]:
    from specter.data.roles import (
        CANONICAL_ROLE_IDS,
        articles_for_role,
        get_role_obligation,
    )

    role_id = (role or "").strip()
    if role_id not in CANONICAL_ROLE_IDS:
        return {
            "found": False,
            "role": role,
            "valid_roles": list(CANONICAL_ROLE_IDS),
        }

    obligation = get_role_obligation(role_id)
    if obligation is None:
        return {"found": False, "role": role_id, "valid_roles": list(CANONICAL_ROLE_IDS)}

    primary = list(articles_for_role(role_id, include_secondary=False))
    secondary = [a for a in articles_for_role(role_id) if a not in primary]

    return {
        "found": True,
        "role": role_id,
        "label": obligation.get("label", ""),
        "definition": obligation.get("definition", ""),
        "article_count_primary": len(primary),
        "article_count_secondary": len(secondary),
        "primary_articles": primary,
        "secondary_articles": secondary,
    }


def _judge_proposal(proposal: dict[str, Any], valid_dimensions: list[str]) -> dict[str, Any]:
    from specter.data.articles_existence import ARTICLE_EXISTENCE
    from specter.judge.reward_hack import (
        ComplianceRewardHackDetector,
        RawProposal,
        ResearchGoal,
        make_eu_ai_act_policy,
    )

    try:
        raw = RawProposal(**proposal)
    except Exception as exc:  # noqa: BLE001 — surface validation errors to caller
        return {"blocked": True, "reasons": [f"proposal_parse_error: {exc}"], "origin": None}

    policy = make_eu_ai_act_policy(
        article_existence=ARTICLE_EXISTENCE,
        valid_dimensions=frozenset(valid_dimensions),
    )
    goal = ResearchGoal(target_value=0.8, max_iterations=30)
    detector = ComplianceRewardHackDetector(
        accepted_proposals=[], answers={}, goal=goal, policy=policy,
    )
    flags = detector.check(raw)
    return {
        "blocked": flags.blocked,
        "reasons": list(flags.reasons),
        "origin": flags.origin,
        "max_registry_overlap": round(flags.max_registry_overlap, 3),
        "max_accepted_overlap": round(flags.max_accepted_overlap, 3),
        "matched_rationalization_entries": list(flags.matched_rationalization_entries),
    }


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    args = arguments or {}
    try:
        if name == "specter_check_article":
            return _wrap(_check_article(args.get("ref", "")))
        if name == "specter_format_citation":
            return _wrap(_format_citation(args.get("ref", "")))
        if name == "specter_list_articles":
            return _wrap(_list_articles(args.get("kind", "all")))
        if name == "specter_apts_self_conformance":
            return _wrap(_apts_self_conformance())
        if name == "specter_apts_requirement":
            return _wrap(_apts_requirement(args.get("requirement_id", "")))
        if name == "specter_get_taxonomy":
            return _wrap(_get_taxonomy())
        if name == "specter_role_obligations":
            return _wrap(_role_obligations(args.get("role", "")))
        if name == "specter_judge_proposal":
            return _wrap(
                _judge_proposal(
                    args.get("proposal", {}),
                    args.get("valid_dimensions", []),
                ),
            )
        return _wrap({"error": f"unknown tool: {name}"})
    except Exception as exc:  # noqa: BLE001 — never crash the MCP loop
        return _wrap({"error": f"{type(exc).__name__}: {exc}"})


async def main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
