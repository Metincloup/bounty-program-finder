# Data Source Strategy

## Source Priority

1. Official platform APIs or official program pages.
2. GitHub repository APIs for repository metadata.
3. Seed data from public bounty target dumps.
4. Search inference, only with low confidence and clear labeling.

## Seed Source Policy

Use `arkadiyt/bounty-targets-data` to quickly find candidate programs and scopes. Mark it as `seed` and require official verification before test authorization.

## Credential Policy

Credentials are optional. Read them only from environment variables:

- `GITHUB_TOKEN`
- `HACKERONE_USERNAME`
- `HACKERONE_TOKEN`
- `BUGCROWD_TOKEN_ID`
- `BUGCROWD_TOKEN_SECRET`
- `INTIGRITI_TOKEN`
- `YESWEHACK_ACCESS_TOKEN`

When credentials are missing, return partial results with `unknown` or `unavailable` fields instead of inventing data.

## Cache Policy

- Store fetched data under `.cache/bounty-program-finder/`.
- Honor `--refresh` to bypass stale cache.
- Include source timestamps in output.
- Keep `.cache/` ignored by git.

## Confidence Labels

- `verified`: official evidence supports the claim.
- `high`: explicit scope or official linkage, but not fully revalidated in the current run.
- `medium`: seed data or strong public metadata.
- `low`: search inference or weak linkage.
- `unknown`: data unavailable.
