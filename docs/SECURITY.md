# Security & Secrets

This document covers secrets handling, Redis exposure, and basic hygiene for this POC.

## Secrets handling
- Polygon API key is loaded from `.env` (`POLYGON_API_KEY`)
- `.env` is excluded via `.gitignore`
- Do not commit real keys; use `.env.example` to share variable names
- In CI or production, prefer environment variables or secret managers (e.g., AWS Secrets Manager, GCP Secret Manager)

## Redis exposure
- Default Redis is bound to localhost via docker-compose port exposure (6379)
- For production-like setups:
  - Run Redis behind a private network or VPC
  - Enable Redis AUTH and TLS if traffic crosses trust boundaries
  - Restrict firewall rules to only trusted hosts/services

## Principle of least privilege
- Scope API keys to read-only where possible
- Avoid embedding secrets in code or configs that may be shared

## Files and permissions
- Ensure data directories are writable by the service user only
- Rotate logs that may contain operational details; avoid logging secrets

## Additional considerations (beyond POC)
- Use a secrets vault instead of .env
- Audit logs for ingress/egress
- Network policies to isolate Redis and service containers
