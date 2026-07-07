# Platform Notes

## HackerOne

Seed data often includes program name, handle, URL, bounty availability, response efficiency, average time to first response, average time to bounty, and structured scope targets.

Official enrichment can use HackerOne API credentials when present. Without credentials, mark official enrichment unavailable.

## Bugcrowd

Seed data often includes program URL, safe harbor, max payout, disclosure setting, managed-by-Bugcrowd status, and targets.

Bugcrowd API data uses JSON:API conventions. Preserve target groups and exclusions when available.

## Intigriti

Seed data often includes status, confidentiality level, minimum and maximum bounty, terms acceptance, two-factor requirements, and targets.

The researcher API may be beta or access-controlled. Label unavailable fields clearly.

## YesWeHack

Seed data often includes public/disabled flags, min/max bounty, and targets.

API access may use OAuth or PAT flows. The v1 skill should not perform interactive auth; rely on environment-provided tokens.

## GitHub

Use GitHub API metadata for stars, forks, language, license, topics, and recent push time. Explicit GitHub scope entries are stronger than inferred repository matches.
