# Product Brief

## Goal

Build a reusable Agent Skill that helps a security researcher discover bug bounty programs that match a requested research strategy, especially programs with in-scope open-source GitHub repositories.

## Primary User

A security researcher who wants to choose a bounty target before using a separate audit or pentest workflow.

## Success Criteria

- Return a ranked shortlist with clear evidence and caveats.
- Explain why each candidate matches the user's criteria.
- Preserve scope, exclusions, payout, response, and requirement information.
- Include repository links and confidence labels for GitHub matches.
- Provide a safe handoff to a separate audit prompt without performing the audit.
- Work without credentials using seed/public data, and improve results when credentials are present.

## Non-Goals

- Do not scan targets.
- Do not exploit vulnerabilities.
- Do not submit reports.
- Do not decide that a target is authorized based on inferred data.
- Do not store secrets in source, output, generated packages, or tests.
