# Output Contract

## Human Output

Return:

- Ranked Markdown table.
- Per-program detail cards.
- Scope evidence and exclusions.
- GitHub repository candidates with confidence labels.
- Payout and response metrics.
- Warnings and verification requirements.
- Recommended next-step clone/build hints when safe to suggest.

## JSON Output

Top-level fields:

- `schema_version`
- `generated_at`
- `query`
- `filters`
- `profile`
- `source_summary`
- `results`
- `master_prompt_handoff`

`source_summary.query_inference` records direct CLI query inference.

Each result must include:

- `id`
- `program`
- `visibility`
- `bounty`
- `metrics`
- `scope`
- `github_repos`
- `requirements`
- `score`
- `confidence`
- `warnings`
- `sources`
- `master_prompt_handoff`

## Missing Data

Use `unknown` for unavailable fields. Do not infer payout, authorization, or private program details without source evidence.
