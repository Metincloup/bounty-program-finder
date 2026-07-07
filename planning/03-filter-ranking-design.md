# Filter And Ranking Design

## Filter Families

- Platform: HackerOne, Bugcrowd, Intigriti, YesWeHack.
- Visibility: public, private, invite-only, unknown.
- Reward: bounty-only, VDP, min payout, max payout, currency.
- Scope: URL, wildcard, API, mobile, desktop, source code, smart contract, other.
- GitHub: required, explicit in scope, inferred, language, stars, forks, topics, license, activity.
- Requirements: KYC, 2FA, reputation, terms acceptance.
- Operations: response efficiency, time to first response, time to bounty, recent activity.
- Safety: out-of-scope text, exclusions, safe harbor, confidence threshold.

## Profiles

- `balanced`: combine reward, scope clarity, GitHub quality, response metrics, and confidence.
- `oss_audit`: prioritize explicit GitHub scope, repo metadata, buildability hints, and high confidence.
- `max_payout`: prioritize max reward and payout evidence.
- `fast_response`: prioritize response efficiency and response-time metrics.
- `popular`: prioritize repo stars, forks, public traction, and program recognizability.
- `low_noise`: use available friction and competition proxies; label uncertainty.

## Scoring Principles

- Scores must be explainable.
- Missing values should not become zero silently; include missing-data reasons.
- Derived metrics must be labeled.
- Scope confidence should gate final recommendations more strongly than payout.
