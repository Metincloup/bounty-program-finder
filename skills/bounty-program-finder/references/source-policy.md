# Source Policy

## Trust Levels

- `official`: official API response or official program page.
- `github_api`: GitHub REST API metadata.
- `seed`: public dump used for candidate discovery.
- `inferred`: search or heuristic linkage.

## Authorization

Only official scope evidence can support an authorization recommendation. Seed data, repository search, and homepage inference are candidate signals.

Use these statuses:

- `official_scope_verified`
- `candidate_verification_required`
- `not_authorized_or_out_of_scope`
- `unknown`

## Missing Data

Use `unknown` when a field is unavailable. Use `derived` only when the computation and source are shown.

## Credentials

Read credentials only from environment variables. Do not write tokens to cache, output, logs, or generated packages.

## Cache

Cache responses under `.cache/bounty-program-finder/`. The cache is a local performance feature, not a source of truth.
