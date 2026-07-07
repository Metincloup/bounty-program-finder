# Project Memory

## Locked Decisions

- Skill name: `bounty-program-finder`.
- Scope: discovery, filtering, ranking, explanation, and audit handoff only.
- Non-goals: vulnerability discovery, scanning, exploitation, fuzzing, cloning by default, running target code, or report submission.
- v1 platforms: HackerOne, Bugcrowd, Intigriti, YesWeHack, and GitHub enrichment.
- Seed source: `arkadiyt/bounty-targets-data` is useful for fast discovery but is not authoritative.
- Output: rich Markdown plus stable JSON.
- CLI input: exact `--filters-json` plus heuristic `--query` for direct natural-language use.
- Language: skill files and schema keys are English; user-facing prose follows the user.
- Dependencies: Python stdlib only for v1.
- Cache: workspace cache under `.cache/bounty-program-finder/`, ignored by git.
- Private program handling: include private or invite-only programs when accessible through user credentials and clearly label them.
- Private prompt handling: do not copy, package, commit, or require private prompt repositories.

## Open-Source Readiness

- Keep secrets, cache, generated packages, and private prompt material out of source control.
- Avoid user-specific paths in skill resources.
- Keep platform credentials in environment variables only.
- Treat third-party dumps as cache/seed inputs, not trusted official scope.

## Deferred

- Immunefi and HackenProof adapters.
- Interactive OAuth helpers.
- Full official API coverage for every platform endpoint.
- Persistent user profiles beyond JSON filters.
- Automated repository cloning or build orchestration.
