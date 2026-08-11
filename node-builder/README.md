# Node.js + OpenJDK 17 Build Image

A build/CI Docker image based on **Node.js 22 (Alpine)** with **OpenJDK 17**, `rsync`, `git`,
and a complete `node-gyp` toolchain pre-installed. It is intended for compiling applications
and running multi-language CI/CD jobs — not for serving traffic.

### What is node-builder?

`node-builder` is the **build** half of the Node build/run split. It installs dependencies
and compiles the app; [`node-runtime`](../node-runtime) is the lean, non-root image that
actually serves the result in production.

The two images are deliberately kept on the **same base** — Alpine (musl) and **Node 22** —
so that a `node_modules` tree produced here is binary compatible with the runtime. See
[Why Alpine and why pinned](#why-alpine-and-why-pinned).

---

## Features

- **Node.js 22 LTS** (pinned), npm, and npx.
- **OpenJDK 17 JRE** for running Java tooling and JAR-based build steps.
- **`node-gyp` toolchain** (`python3`, `make`, `g++`) so dependencies that must compile from
  source build successfully.
- **`git`** for npm dependencies referenced by git URL and for CI checkouts.
- **`rsync`**, `curl`, `openssl`, and `ca-certificates` for sync/deploy and HTTPS steps.
- **`bash`** as the default shell, for CI scripts that assume it.
- Starts in the `/app` working directory.

### Why Alpine and why pinned

Both choices exist to keep this image binary compatible with
[`node-runtime`](../node-runtime):

- **Alpine (musl)**: npm resolves platform-specific prebuilt binaries — `sharp`,
  `@next/swc`, `@swc`, and any native addon — for the C library it installs *on*. Building
  on Debian/glibc and running on the Alpine runtime makes `sharp` fall back to its much
  slower WASM build, and breaks native addons that have no fallback.
- **Node 22, not `lts`**: `node:lts` now resolves to Node 24. Building with a different Node
  major than the runtime executes can produce incompatible output, so the major is pinned
  here and upgraded deliberately in step with `node-runtime`.

Because Alpine publishes fewer prebuilt binaries than Debian, compile-from-source happens
more often on musl — hence the bundled `python3`/`make`/`g++`, without which those installs
fail with `gyp ERR! find Python`.

---

## Usage

### Pull from GitHub Container Registry

```sh
docker pull ghcr.io/idbi/docker-node-builder:latest
```

**Available tags:**
- `ghcr.io/idbi/docker-node-builder:latest` — Latest stable release
- `ghcr.io/idbi/docker-node-builder:X.Y.Z` — Specific version
- `ghcr.io/idbi/docker-node-builder:X` — Latest patch for a major version

### Build Locally

```sh
docker build -t node-builder:latest ./node-builder
```

### Run an Interactive Shell

```sh
docker run -it --rm -v "$PWD":/app ghcr.io/idbi/docker-node-builder:latest
```

### Use as a build stage

The intended pattern — compile here, ship on `node-runtime`:

```dockerfile
# syntax=docker/dockerfile:1
FROM ghcr.io/idbi/docker-node-builder:latest AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM ghcr.io/idbi/docker-node-runtime:latest
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
```

See the [`node-runtime` README](../node-runtime/README.md) for the full Next.js standalone
contract.

### Use as a CI/CD Build Runner

This image is suitable for:

- Installing dependencies and building Node.js applications
- Running Java (JAR) CLI tools alongside Node tooling — e.g. OpenAPI generators, schema
  validators, Selenium
- Multi-language continuous integration jobs
- Deployment steps that need `rsync` or `git`

---

## Verifying the Image

```sh
docker run --rm node-builder:latest node -v      # -> v22.x.y
docker run --rm node-builder:latest npm -v
docker run --rm node-builder:latest java -version # -> openjdk 17.x
docker run --rm node-builder:latest bash -c 'command -v git rsync curl python3 make g++'
```

---

## Troubleshooting

### `gyp ERR! find Python` or a failing native module build
The toolchain is present in this image, so this usually means the build runs in a different
stage or image. Confirm the failing step actually executes in `node-builder`.

### A native module works here but fails on `node-runtime`
Almost always a base mismatch — check that the runtime stage is `node-runtime` (Alpine) and
not a Debian image, and that both are on the same Node major.

### `Error loading shared library` for a package installed elsewhere
`node_modules` was installed on glibc and copied into an Alpine image. Install dependencies
in this image rather than copying a tree built on Debian/Ubuntu.

---

## Image Information

- **Base Image**: `node:22-alpine`
- **Java**: OpenJDK 17 (JRE)
- **User**: `root` (build image — the runtime image is the non-root one)
- **Working Directory**: `/app`
- **Architectures**: `linux/amd64`
- **Version**: see [CHANGELOG.md](CHANGELOG.md) for release history

---

**Contact:** IDBI DevOps Team · [devops@idbi.pe](mailto:devops@idbi.pe)
