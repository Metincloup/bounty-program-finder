# Master Prompt Handoff

Use this generic structure when the user may continue from discovery into a separate audit workflow.

```json
{
  "target_name": "Program or repository name",
  "repository_url": "https://github.com/owner/repo",
  "repository_path_suggestion": "./repo",
  "build_or_run_command_suggestion": "unknown",
  "main_binary_or_service": "unknown",
  "test_environment": "local lab only; do not contact production or third-party systems",
  "disclosure_platform_or_program": "Platform / Program URL",
  "scope_evidence": [],
  "exclusions": [],
  "warnings": [],
  "authorization_status": "candidate_verification_required"
}
```

Rules:

- Keep this generic. Do not reference private prompt names or private prompt text.
- Use `unknown` rather than inventing build or service details.
- Include repository clone hints separately from handoff fields.
- If official scope is not verified, set `authorization_status` to `candidate_verification_required`.
