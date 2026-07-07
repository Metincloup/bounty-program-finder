# Output Contract

Return both human-readable Markdown and machine-readable JSON unless the user asks for one format.

## Markdown

Use this order:

1. Short summary of filters and source freshness.
2. Ranked table with score, program, platform, bounty, GitHub match, scope status, and confidence.
3. Per-program detail cards with:
   - program URL
   - reward range
   - response or payout metrics
   - in-scope highlights
   - out-of-scope warnings
   - GitHub repository candidates
   - recommended next step
4. Safety note: do not test until official scope is verified.

## JSON

Emit a fenced JSON block with:

```json
{
  "schema_version": "1.0.0",
  "generated_at": "ISO-8601 UTC timestamp",
  "query": "original user request or null",
  "filters": {},
  "profile": "balanced",
  "source_summary": {},
  "results": [],
  "master_prompt_handoff": []
}
```

`source_summary.query_inference` should show the original `--query`, inferred filters, inferred profile, explicit profile flag, and effective profile.

Each `results[]` item must include:

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

Keep JSON field names stable and English.
