# Node.js + OpenJDK 17 Build Image

A build/CI Docker image based on **Alpine**, published for **Node 18, 20, 22 and 24**, with
**OpenJDK 17**, `rsync`, `git`, and a complete `node-gyp` toolchain pre-installed. It is
intended for compiling applications and running multi-language CI/CD jobs — not for serving
traffic.

Every Node major is built from this one Dockerfile — see [Node versions](#node-versions) for
the tag matrix and support status.

### What is node-builder?

`node-builder` is the **build** half of the Node build/run split. It installs dependencies
and compiles the app; [`node-runtime`](../node-runtime) is the lean, non-root image that
actually serves the result in production.

The two images are published from the **same base** — Alpine (musl) — and for the **same set
of Node majors**, so that a `node_modules` tree produced here is binary compatible with the
runtime **when the two tags name the same major**. See
[Why Alpine and why pinned](#why-alpine-and-why-pinned).

---

## Features

- **Node 18 / 20 / 22 / 24** — one major pinned per image — plus npm and npx.
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
- **A pinned major, not `lts`**: `node:lts` moves between majors on its own schedule.
  Building with a different Node major than the runtime executes can produce incompatible
  output, so every tag here pins exactly one major, and the same four majors are published
  for `node-runtime`. Choosing the pair is up to you — see [Node versions](#node-versions).

Because Alpine publishes fewer prebuilt binaries than Debian, compile-from-source happens
more often on musl — hence the bundled `python3`/`make`/`g++`, without which those installs
fail with `gyp ERR! find Python`.

---

## Node versions

One image is published per supported Node major, identical apart from the base. The same
majors are published for [`node-runtime`](../node-runtime), so every build tag has a runtime
counterpart.

| Node | Tag | Upstream status | Upstream EOL | Bundled npm |
| ---- | --- | --------------- | ------------ | ----------- |
| 24 | `:node24` | Active LTS | 2028-04-30 | 11.x |
| 22 | `:node22` — also `:latest` | Maintenance LTS | 2027-04-30 | 10.x |
| 20 | `:node20` | **End of life** | 2026-04-30 | 10.x |
| 18 | `:node18` | **End of life** | 2025-04-30 | 10.x |

> **Node 18 and 20 are past their upstream end-of-life** and receive no further security
> patches from the Node project. They are published here only to keep existing services
> building while they are migrated. Use `:node24` for anything new.

Because the Node 18 base sits on an older Alpine release, its OpenJDK and system packages are
correspondingly older too — another reason not to start new work there.

**Always match the major to the runtime tag you deploy on.** A `node_modules` tree with
compiled addons built on Node 24 will not load on Node 20.

---

## Usage

### Pull from GitHub Container Registry

```sh
docker pull ghcr.io/idbi/docker-node-builder:node22   # pin the Node major
docker pull ghcr.io/idbi/docker-node-builder:latest   # == :node22 today
```

**Available tags** — each release publishes, for every Node major:
- `ghcr.io/idbi/docker-node-builder:X.Y.Z-node22` — Exact image version, on Node 22
- `ghcr.io/idbi/docker-node-builder:X-node22` — Latest patch of image major `X`, on Node 22
- `ghcr.io/idbi/docker-node-builder:node22` — Latest release, on Node 22

…and the same three shapes for `node18`, `node20` and `node24`. The default major (22) also
takes the unsuffixed `:latest`, `:X.Y.Z` and `:X` tags.

### Build Locally

```sh
# Default major (22), identical to what :latest is built from
docker build -t node-builder:latest ./node-builder

# A specific major
docker build --build-arg NODE_VERSION=24 -t node-builder:node24 ./node-builder
```

### Run an Interactive Shell

```sh
docker run -it --rm -v "$PWD":/app ghcr.io/idbi/docker-node-builder:node22
```

### Use as a build stage

The intended pattern — compile here, ship on `node-runtime`:

```dockerfile
# syntax=docker/dockerfile:1
# Same major on both stages — mixing them breaks compiled native addons.
FROM ghcr.io/idbi/docker-node-builder:node22 AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM ghcr.io/idbi/docker-node-runtime:node22
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
```

Prefer the explicit `node<major>` tags over `:latest` here: the build and runtime tags
resolve independently, so `:latest` on both would silently split the pair if the default
major ever changes.

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
docker run --rm node-builder:latest node -v      # -> v22.x.y (matches the tag)
docker run --rm node-builder:latest npm -v
docker run --rm node-builder:latest java -version # -> openjdk 17.x
docker run --rm node-builder:latest bash -c 'command -v git rsync curl python3 make g++'

# Which base the image was built from, without running it
docker image inspect node-builder:latest \
    --format '{{index .Config.Labels "org.opencontainers.image.base.name"}}'
```

---

## Troubleshooting

### `gyp ERR! find Python` or a failing native module build
The toolchain is present in this image, so this usually means the build runs in a different
stage or image. Confirm the failing step actually executes in `node-builder`.

### A native module works here but fails on `node-runtime`
Almost always a base mismatch — check that the runtime stage is `node-runtime` (Alpine) and
not a Debian image, and that both tags name the **same Node major**. A `NODE_MODULE_VERSION`
error in the runtime container is this mismatch by definition.

### `Error loading shared library` for a package installed elsewhere
`node_modules` was installed on glibc and copied into an Alpine image. Install dependencies
in this image rather than copying a tree built on Debian/Ubuntu.

---

## Image Information

- **Base Image**: `node:<major>-alpine`, built for majors **18, 20, 22, 24** (`:latest` = 22)
- **Java**: OpenJDK 17 (JRE)
- **User**: `root` (build image — the runtime image is the non-root one)
- **Working Directory**: `/app`
- **Architectures**: `linux/amd64`
- **Version**: see [CHANGELOG.md](CHANGELOG.md) for release history

---

**Contact:** IDBI DevOps Team · [devops@idbi.pe](mailto:devops@idbi.pe)
