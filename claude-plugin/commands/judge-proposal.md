# /specter:judge-proposal

Run a roadmap-task proposal through the **ComplianceRewardHackDetector**
(LLM-as-Judge). Six checks, in order:

1. **Plagiarism + origin detection** — SequenceMatcher on prompt vs
   prior-task registry / accepted proposals; ≥0.80 overlap rejects
   AND labels `registry_lift`; 0.50–0.79 vs accepted labels
   `recombination`; otherwise `agent_novel`.
2. **KB reality** — `article_paragraphs` resolve against the
   regulation catalog; `dimension_id` resolves against the host's
   compliance-dimension set.
3. **Coverage plausibility** — per-dimension cap: a single proposal
   can claim at most `open_questions / total_questions` worth of
   coverage gain.
4. **Effort sanity** — within `goal.max_effort_hours_per_task` and
   above 0.5h floor.
5. **Contract completeness** — ≥2 acceptance_criteria, ≥1
   output_file, ≥1 contract_verification.
6. **Rebutted-excuse match** — token-Jaccard per-sentence; hard
   matches block, soft matches recorded for telemetry.

Per the upstream design contract, the detector OWNS the `origin`
label — the agent's self-claim is ignored, eliminating the "lying
agent self-labels as agent_novel when it actually plagiarised" attack
surface.

## Usage

```
/specter:judge-proposal proposal=<json> valid_dimensions=<array>
```

Example proposal payload:

```json
{
  "task_id": "t1",
  "task_title": "Establish risk management system",
  "description": "Document Art. 9 risk management process for the deployed system.",
  "agent": "compliance_officer",
  "priority": "P1",
  "effort_hours": 8.0,
  "dimension_id": "risk_management",
  "prompt": "Set up an Article 9 risk-management workflow + RAID log",
  "acceptance_criteria": ["RAID log exists", "Workflow documented"],
  "output_files": ["docs/risk-management.md"],
  "article_paragraphs": ["Art. 9"],
  "contract_verification": [{"cmd": "pytest tests/test_risk_management.py"}]
}
```

`valid_dimensions`: `["risk_management", "transparency", "data_governance", ...]`

## Returns

```json
{
  "blocked": false,
  "reasons": [],
  "origin": "agent_novel",
  "max_registry_overlap": 0.0,
  "max_accepted_overlap": 0.0,
  "matched_rationalization_entries": []
}
```

When blocked:

```json
{
  "blocked": true,
  "reasons": ["kb_reality: article_paragraphs ['Art. 999'] not found in the regulation catalog"],
  "origin": "agent_novel",
  ...
}
```

## When to use

- Validating an LLM-proposed remediation task before persisting it
  to the roadmap
- Auditing a roadmap for hallucinated article citations or
  cargo-cult plagiarism from a registry
- Running the judge on every iteration of a Karpathy-style
  autoresearch loop to gate accept-vs-reject

Wraps `specter.judge.reward_hack.ComplianceRewardHackDetector` via
the `specter_judge_proposal` MCP tool.
