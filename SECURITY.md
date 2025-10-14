# Security Policy

- Please report security issues privately to the maintainer: Rodrigo Oliveira <rodrfons@hotmail.com>
- Do not open public issues for potential vulnerabilities.
- Rotate any credentials you suspect may have been exposed.

Notes for maintainers
- The .env file should not be committed. Use .env.example for guidance.
- The Polygon API key shown in previous revisions must be rotated before public release.
- Optional CI leak scanning can be enabled by setting repo Variable ENABLE_LEAK_SCAN=1.
  - If you have a gitleaks license, store it as Secret GITLEAKS_LICENSE (not required for OSS use).
