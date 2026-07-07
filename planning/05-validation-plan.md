# Validation Plan

## Static Validation

- Run the Codex skill validator against `skills/bounty-program-finder`.
- Run Python unit tests with stdlib `unittest`.
- Ensure generated Claude packages exclude cache, secrets, dist noise, and private prompt material.

## Behavior Tests

- Normalize representative HackerOne, Bugcrowd, Intigriti, and YesWeHack seed records.
- Run without credentials and verify degraded-but-useful output.
- Mock credential-present behavior and verify private labels.
- Ensure inferred GitHub repositories are not marked authorized.
- Ensure Markdown and JSON output parse cleanly.
- Ensure `master_prompt_handoff` contains generic audit starter fields.

## Safety Tests

- A seed-only GitHub scope must remain `candidate_verification_required`.
- Out-of-scope targets must stay visible.
- Clone/build commands must be recommendations only.
- Tokens and `.env` values must never appear in output.
