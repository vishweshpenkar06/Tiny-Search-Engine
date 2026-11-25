# Secrets in Containers

Secrets such as admin passwords belong in environment variables injected at runtime, never in a built image. A committed .env.example should contain names and safe defaults only.

Generate password hashes with a slow hash function and compare them in constant time. Rotate credentials when a person with access leaves the team.

Scan repositories for key patterns in CI and keep build caches out of published artifacts. A leaked key must be revoked, not merely deleted.
