# Filter Schema

Use this schema when translating natural language into `--filters-json`. The CLI also accepts `--query` for heuristic natural-language inference; explicit JSON filters override inferred query filters.

```json
{
  "query": "original user intent",
  "platforms": ["hackerone", "bugcrowd", "intigriti", "yeswehack"],
  "visibility": ["public", "private", "invite-only", "unknown"],
  "bounty_only": true,
  "min_payout": 1000,
  "currency": "USD",
  "require_github": true,
  "github_match": ["explicit", "official_link", "inferred"],
  "languages": ["python", "go", "javascript"],
  "min_stars": 1000,
  "min_forks": 100,
  "scope_types": ["url", "api", "source_code", "wildcard"],
  "topics": ["security", "api"],
  "safe_harbor_required": false,
  "exclude_requirements": ["kyc", "reputation"],
  "min_confidence": 0.5,
  "keywords": ["github", "open source", "popular"]
}
```

All fields are optional. Prefer conservative filters when the user is ambiguous:

- Use `require_github: true` only when the user asks for open-source, GitHub, repository, code audit, or source review targets.
- Use `bounty_only: true` when the user asks for bounty, payout, reward, or paid programs.
- Use `platforms` only when the user names platforms.
- Use `keywords` for weak textual hints that should not hard-filter results.

Supported ranking profiles:

- `auto`
- `balanced`
- `oss_audit`
- `max_payout`
- `fast_response`
- `popular`
- `low_noise`
