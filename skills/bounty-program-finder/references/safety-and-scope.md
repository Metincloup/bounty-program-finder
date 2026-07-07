# Safety And Scope

This skill is a discovery tool. It must not perform security testing.

## Required Rules

- Do not scan, fuzz, exploit, or probe targets.
- Do not clone or build repositories automatically.
- Do not submit reports.
- Do not claim that a target is authorized from seed or inferred data alone.
- Always preserve exclusions and out-of-scope text.
- Recommend official brief verification before any audit begins.

## GitHub Repository Handling

Classify repository matches:

- `explicit_scope`: repository URL appears in scope data.
- `official_link`: repository is linked by an official program or official site.
- `inferred`: repository was found by search or name matching.

Only `explicit_scope` with official evidence should be treated as ready for an audit handoff. Seed-only explicit scope still requires verification.

## Clone And Build Hints

Provide clone/build hints as text only:

```bash
git clone <repo_url>
cd <repo_name>
# inspect README/package files before running build commands
```

Do not run these commands as part of discovery.
