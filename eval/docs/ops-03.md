# Compose Networking

Docker Compose creates a private bridge network for a project. Services reach each other by service name, so the frontend calls the backend without knowing its host address.

Only the service that serves users should publish a host port. Keeping internal services unexposed reduces the attack surface.

Named volumes survive container replacement and should hold all durable state. Use tmpfs for scratch data that must never be persisted.
