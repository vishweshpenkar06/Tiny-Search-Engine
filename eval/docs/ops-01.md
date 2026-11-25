# Docker Multi Stage Builds

A multi stage Dockerfile separates build tools from the runtime image. The builder stage compiles dependencies, and the final stage copies only what the application needs at runtime.

This reduces image size and attack surface because compilers and package caches never ship. Pin base images by digest for reproducible builds.

Run as a non root user and set a read only filesystem where possible. A healthcheck lets orchestrators replace a stuck container.
