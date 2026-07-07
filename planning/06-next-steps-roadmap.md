# Next Steps Roadmap

## Immediate Hardening

- Review a few real discovery outputs manually and tune scoring weights.
- Add offline fixtures that mimic larger seed payloads and edge cases.
- Add snapshot-style tests for Markdown structure and JSON schema stability.
- Add cache metadata tests for TTL, refresh, and cache-hit behavior.
- Add packaging checks that generated Claude zips contain no cache, `.env`, or generated noise.

## Official Source Deepening

- Implement one official platform adapter at a time, starting with HackerOne because its hacker API and structured scope model are the clearest fit.
- Add authenticated fixtures for each official adapter without storing secrets.
- Keep official API enrichment separate from seed normalization so platform failures degrade cleanly.
- Add source freshness and endpoint capability fields per platform.
- Preserve strict authorization gates: official reachability or credentials must not automatically mean scope authorization.

## GitHub Enrichment

- Add repository build-system detection from GitHub API contents or cloned metadata only when explicitly requested.
- Add better organization/homepage matching with stronger false-positive controls.
- Add topic/license filtering once fixture coverage exists.
- Add recent-activity scoring based on `pushed_at` age.

## UX And Workflow

- Add reusable query examples for common hunter profiles.
- Add optional YAML profile files if repeated personal workflows become useful.
- Add an install/sync script for copying the validated skill to `~/.codex/skills/`.
- Add a command that emits only the `master_prompt_handoff` block for a selected result.

## Platform Expansion

- Evaluate Immunefi and HackenProof as separate adapters after v1 stabilizes.
- Decide whether Web3 programs should be a separate profile or a separate skill.
- Add support for additional public disclosure/program indexes only as seed sources.

## Release Readiness

- Add a first commit after reviewing staged files.
- Run a clean clone test.
- Run tests with no network using fixtures only.
- Run one network smoke test before release.
- Tag a first internal version before any public release.
