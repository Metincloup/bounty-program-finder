---
name: bounty-program-finder
description: Find, filter, rank, and explain bug bounty programs and in-scope GitHub repositories. Use for bounty discovery, scope triage, payout/response metrics, and audit handoff.
---

# Bounty Program Finder

## Overview

Use this skill to help a security researcher select bug bounty programs before a separate audit workflow begins. It produces candidate programs, scope evidence, GitHub repository matches, payout and response signals, safety warnings, and a structured handoff for an audit prompt.

This skill is discovery-only. Do not scan, fuzz, exploit, clone repositories, run target code, or submit reports as part of this workflow.

## Workflow

1. Clarify the discovery intent only when needed: target platforms, bounty type, GitHub requirement, languages, payout expectations, popularity, response speed, or private-program inclusion.
2. Convert the user's natural-language request into the filter schema in `references/filter-schema.md`.
3. Run the bundled CLI when local execution is useful:

```bash
python skills/bounty-program-finder/scripts/bounty_program_finder.py \
  --query "List popular in-scope bounty programs with open-source GitHub repositories" \
  --profile auto \
  --limit 10 \
  --format both
```

4. Use `--filters-json` when exact repeatability is needed; explicit JSON filters override inferred query filters.
5. Review the result warnings before presenting any target as suitable. Treat seed-only matches as candidates until official scope evidence is checked.
6. Return rich Markdown plus the JSON block described in `references/output-contract.md`.
7. Include the generic audit handoff from `references/master-prompt-handoff.md` when the user may continue into a separate audit prompt.

## Reference Routing

- Read `references/filter-schema.md` when translating user requests into filters.
- Read `references/source-policy.md` before deciding whether data is verified, seed-only, derived, private, or stale.
- Read `references/platform-notes.md` when explaining platform-specific capabilities or missing fields.
- Read `references/output-contract.md` before changing the result shape.
- Read `references/safety-and-scope.md` whenever a result includes repositories, scope, exclusions, or testing suggestions.
- Read `references/master-prompt-handoff.md` when producing next-step handoff fields for a separate audit workflow.

## CLI Defaults

- Default limit: 10 rich records.
- Default profile flag: `auto`; it resolves to `balanced` unless the query implies a specialized profile.
- Default cache: `.cache/bounty-program-finder`.
- Default source flow: seed data first, then official or public enrichment when available.
- Credentials are optional and must come from environment variables only.
- User-facing prose should follow the user's language; JSON field names stay English.

## Safety Rules

- Never mark a repository or asset as authorized unless official scope evidence supports it.
- Preserve out-of-scope targets and exclusions close to the relevant candidate.
- Label inferred GitHub repositories as candidates unless they are explicitly present in official scope or have verified official linkage.
- Provide clone/build commands only as recommendations for the user's next step; do not run them.
- Never store or reveal API tokens, private prompt text, `.env` content, cache dumps, or private program details beyond the user's requested output.
