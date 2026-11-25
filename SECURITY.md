# Security Policy

## Scope

This project is a local search engine. It is not a multi-tenant service and has no accounts beyond one optional administrator credential. Do not expose it directly to the public internet without a reverse proxy, TLS and a review of the limits below.

## Reporting

If you find a vulnerability, open an issue with a description and a minimal reproduction, or contact the maintainers privately if the issue is sensitive. Include the affected version, configuration and the endpoint involved. Please do not include real credentials in a report.

## Hardening in place

- API routes require HTTP Basic auth when both `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` are set. Health and readiness endpoints stay public for orchestrators.
- Mutating requests require an `Origin` matching `PUBLIC_ORIGIN` when auth is enabled.
- Request bodies are capped by `MAX_CONTENT_LENGTH`; individual uploads are capped by `MAX_FILE_SIZE` and `MAX_FILES`.
- Query length, pagination and threshold values are validated and rejected with stable error codes.
- Upload ids and document ids must be UUIDs; job ids are restricted to a safe character set. No client-supplied path is used as a filesystem path.
- Uploads are written as opaque blob names under a generated directory, so original filenames do not become server paths.
- Responses contain no absolute filesystem paths. Structured logs contain no query text, document content or paths.
- The backend container runs as a non-root user with a read-only root filesystem and no published host port.
- Security headers are added to every response; API responses are marked `no-store`.

## Known limits

- The rate limiter is in-process and per-address. It does not coordinate across replicas; run one backend replica.
- Auth is optional. With it disabled, anyone who can reach the backend network can index and search. Compose keeps that network internal.
- The crawler is opt-in. It can fetch attacker-controlled content, so keep `CRAWLER_ALLOWED_DOMAINS` narrow and do not enable it on untrusted networks.
- Uploaded HTML is parsed as text and returned as `text/plain`, but downstream renderers must still treat content as untrusted.
- No audit log, account model, per-user quotas or CSRF token mechanism exists. Origin checking is the CSRF mitigation for mutating API calls.
- Semantic modes depend on third-party model weights when enabled; review their licence and provenance before production use.

## Secrets

Keep real credentials in runtime environment variables or a secret manager. `.env.example` contains names and safe defaults only. CI scans tracked files for common key patterns. If a credential leaks, revoke it first and then remove it from history.
