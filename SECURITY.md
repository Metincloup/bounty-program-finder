# Security Policy

## Intended Use

This project is a discovery and triage aid for authorized bug bounty research. It does not perform scanning, exploitation, fuzzing, repository cloning, target execution, or report submission.

Do not use output from this tool as proof of authorization. Always verify the official bug bounty program scope, exclusions, and rules before testing any asset.

## Sensitive Data

Do not commit:

- API tokens or credentials.
- `.env` files.
- cache data from `.cache/`.
- private or invite-only program details.
- private prompt repositories or private audit materials.

## Reporting Security Issues

If you find a security issue in this repository, open a private advisory or contact the maintainer privately if a contact channel is available. Do not include live secrets, private program data, or unauthorized target details in public issues.
