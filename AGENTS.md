# AGENTS.md

## Repository overview

This repository is a monorepo of independently built Docker images. Each image lives in its own top-level component directory and uses that directory as its Docker build context. `traefik/` contains deployment configuration only and is not a published image.

Published components are registered in both the root documentation and the Release Please configuration. CI publishes images to GHCR for `linux/amd64` when Release Please creates a component tag such as `node-runtime@v1.2.3`.

## Working conventions

- Keep changes scoped to the affected component unless shared release automation or root documentation must change.
- Treat every component directory as a self-contained build context. Dockerfile `COPY` sources must be relative to that component directory.
- Prefer pinned major or exact dependency versions over floating `latest` tags when changing production base images or downloaded tools.
- Preserve non-root execution, health checks, signal handling, and writable-directory ownership in runtime images.
- Do not commit credentials, private keys, certificates, generated ACME state, or registry tokens.
- Keep a component's `README.md` aligned with its ports, environment variables, build examples, runtime behavior, and verification commands.
- Do not manually edit generated release versions or changelog entries unless the task specifically concerns release metadata; Release Please normally owns them.

## Validation

There is no repository-wide automated test suite. Validate the smallest relevant surface before finishing:

```sh
# Build a changed image from the repository root.
docker build -t local/<component>:test ./<component>

# Check shell syntax for changed scripts.
bash -n path/to/script.sh

# Validate the Traefik Compose configuration when it changes.
docker compose -f traefik/docker-compose.yml config

# Check Release Please JSON when release configuration changes.
jq empty release-please-config.json .release-please-manifest.json

# Exercise release-tag discovery when release automation changes.
./.github/scripts/validate-releases.sh
```

When Docker is unavailable, perform static checks and state clearly that the image build was not run. For runtime images, also run the component-specific smoke or health-check commands documented in its `README.md` when practical.

## Adding or renaming a component

For a publishable image:

1. Add `<component>/Dockerfile`, `<component>/README.md`, and `<component>/CHANGELOG.md`.
2. Put runtime configuration copied by the Dockerfile inside the component directory, conventionally under `<component>/docker/`.
3. Register the component in `release-please-config.json` using the directory name as both the package key and `component` value.
4. Update the root `README.md` component list and repository tree.
5. Leave `.release-please-manifest.json` to Release Please for a new component unless explicitly asked to initialize release state.

Renames also require auditing tags, GHCR image names, downstream `FROM` references, CI configuration, and documentation; do not treat them as directory-only changes.

## Commits and handoff

Use Conventional Commits with the component as the scope when possible, for example `fix(php-fpm): correct health check timeout` or `feat(node-runtime): add runtime dependency`. Use a repository-level scope such as `ci`, `release`, or `docs` for shared changes.

Before handing off, summarize the affected components, list validation performed, and call out any skipped Docker builds or compatibility assumptions.
