# Node.js Runtime for Next.js Applications

A production-ready Docker image based on **Alpine**, published for **Node 18, 20, 22 and
24**, and tuned to run **Next.js** applications built with
[`output: 'standalone'`](https://nextjs.org/docs/app/api-reference/config/next-config-js/output).
It ships `dumb-init` for correct signal handling, an HTTP healthcheck that follows the
configured port, sane production defaults, and runs as a **non-root** user on port **3000**
out of the box.

Every Node major is built from this one Dockerfile — see [Node versions](#node-versions) for
the tag matrix and support status.

### What is node-runtime?

`node-runtime` is the **runtime** half of the Node build/run split — the Node analogue of
[`php-fpm`](../php-fpm). [`node-builder`](../node-builder) is the build image that installs
dependencies and compiles the app; `node-runtime` is the lean image that actually serves
traffic in production.

The two are published from the **same base** — Alpine (musl) — and for the **same set of
Node majors**, so artifacts built on one are binary compatible with the other as long as you
pick matching tags. Plain `node:<major>-alpine` works equally well as a build stage; see
[libc parity](#libc-parity) for why the base matters.

This image deliberately carries **no application code**. You build your app in a separate
stage and `COPY` the Next.js standalone artifacts into a downstream image
(`FROM ghcr.io/idbi/docker-node-runtime`) — see [Usage](#usage).

Unlike the PHP pair, **no web-server sidecar is needed**: the Next standalone server serves
static assets and renders pages itself, so one container is the whole web tier.

### Use Cases

- **Production Next.js SSR/ISR tier**: Run a Next.js app in Docker or Kubernetes with
  graceful shutdown and a working container healthcheck.
- **Immutable deploys**: Ship a small final image containing only the standalone server and
  its pruned `node_modules`, not the full build toolchain or dev dependencies.
- **Consistent runtime**: A single, audited Node base that every Next.js service is built
  on, so Node version upgrades are one deliberate commit here.

---

## Features

### Core
- **Node 18 / 20 / 22 / 24** on **Alpine** — small image, fast cold starts. Each image
  **pins one major**, so a Node upgrade is an explicit change to the tag you deploy, never a
  silent base drift on rebuild.
- **Non-root**: runs as the `node` user (uid `1000`) on port **`3000`**, so it works under
  restricted Kubernetes Pod Security policies without extra privileges.
- **Working directory**: `/app`, with `/app/.next/cache` pre-created and writable so ISR
  revalidation and `next/image` optimization work without a mounted volume.
- **`libc6-compat`** installed for the prebuilt glibc-linked native binaries Next pulls in
  (`@next/swc`, and `sharp` when image optimization is enabled).
- Application logs go to the container's stdout/stderr.

### Signal Handling (`dumb-init`)
- `dumb-init` runs as PID 1 and forwards `SIGTERM`/`SIGINT` to the Node process, so
  `docker stop` and Kubernetes pod termination shut the server down **gracefully** instead
  of being `SIGKILL`ed after the grace period. It also reaps orphaned child processes, which
  Node does not do when it is PID 1 itself.

### Production Defaults
- `NODE_ENV=production` — Next serves the optimized build and skips dev-only work.
- `HOSTNAME=0.0.0.0` — **required**; the Next standalone server binds localhost only by
  default, which is unreachable from outside the container.
- `NEXT_TELEMETRY_DISABLED=1` — no outbound telemetry from production containers.

### Healthcheck
- A `HEALTHCHECK` requests `HEALTHCHECK_PATH` (default `/`) and **asserts an HTTP status
  line**, not merely that a response came back — an unreachable server or a `4xx`/`5xx`
  marks the container unhealthy. It follows `PORT`, so it keeps working when the listen port
  is overridden.
- `2xx` **and** `3xx` both pass, because a Next app's `/` legitimately `307`-redirects under
  i18n or auth middleware. For a strict readiness probe, add a health route to the app and
  point `HEALTHCHECK_PATH` at it (e.g. `/api/health`).

---

## Node versions

One image is published per supported Node major. They are identical apart from the base:
same entrypoint, healthcheck, user, port and environment defaults.

| Node | Tag | Upstream status | Upstream EOL |
| ---- | --- | --------------- | ------------ |
| 24 | `:node24` | Active LTS | 2028-04-30 |
| 22 | `:node22` — also `:latest` | Maintenance LTS | 2027-04-30 |
| 20 | `:node20` | **End of life** | 2026-04-30 |
| 18 | `:node18` | **End of life** | 2025-04-30 |

> **Node 18 and 20 are past their upstream end-of-life** and receive no further security
> patches from the Node project — including for vulnerabilities found in the runtime itself.
> They are published here only to keep existing services building while they are migrated.
> Use `:node24` for anything new, and treat a `:node18` / `:node20` deployment as a
> migration you have not finished yet.

Alpine and the bundled npm also track the base image, so the older majors ship
correspondingly older toolchains (Node 18 ships npm 10, Node 24 ships npm 11).

### Choosing a tag

Pin the **Node major** in your `FROM` line — `:node22`, not `:latest`. The unsuffixed tags
follow whichever major this repository designates as the default (currently **22**, set by
`default` in `node-runtime/variants.json`), so a future change of default would move
`:latest` to a new Node major under any image that tracks it.

Pin the **image version** too for reproducible rebuilds: `:1.0.0-node22` never changes,
`:1-node22` gets patches within major 1, `:node22` follows every release.

---

## Usage

### Pull from GitHub Container Registry

```sh
docker pull ghcr.io/idbi/docker-node-runtime:node22   # pin the Node major
docker pull ghcr.io/idbi/docker-node-runtime:latest   # == :node22 today
```

**Available tags** — each release publishes, for every Node major:
- `ghcr.io/idbi/docker-node-runtime:X.Y.Z-node22` — Exact image version, on Node 22
- `ghcr.io/idbi/docker-node-runtime:X-node22` — Latest patch of image major `X`, on Node 22
- `ghcr.io/idbi/docker-node-runtime:node22` — Latest release, on Node 22

…and the same three shapes for `node18`, `node20` and `node24`. The default major
additionally takes the unsuffixed tags:
- `ghcr.io/idbi/docker-node-runtime:latest` — Latest stable release, on the default major (22)
- `ghcr.io/idbi/docker-node-runtime:X.Y.Z` — Specific version, on the default major
- `ghcr.io/idbi/docker-node-runtime:X` — Latest patch for image major `X`, on the default major

### Build Locally

```sh
# Default major (22), identical to what :latest is built from
docker build -t node-runtime:latest ./node-runtime

# A specific major
docker build --build-arg NODE_VERSION=24 -t node-runtime:node24 ./node-runtime
```

### Recommended: multi-stage build for your app

First, enable standalone output in your app's `next.config.js` / `next.config.ts`:

```js
module.exports = {
  output: 'standalone',
}
```

Then build in one stage and copy the artifacts into this image:

```dockerfile
# syntax=docker/dockerfile:1
# Same Node major on both stages — see "libc parity" below.
FROM ghcr.io/idbi/docker-node-builder:node22 AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM ghcr.io/idbi/docker-node-runtime:node22
# The standalone bundle: server.js + a pruned node_modules.
COPY --from=build --chown=node:node /app/.next/standalone ./
# `standalone` does NOT include these two — they must be copied separately.
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
# ENTRYPOINT ["dumb-init", "--"] and CMD ["node", "server.js"] are inherited.
```

> **The most common mistake**: copying only `.next/standalone`. The app boots and renders,
> but every CSS/JS chunk and every file under `public/` returns `404` — Next excludes
> `.next/static` and `public/` from the standalone output on purpose so they can be served
> from a CDN. Copy both, as above, unless you are fronting the app with a CDN.

Always `COPY --chown=node:node`. Files copied as root are unreadable-for-write by the
runtime user, which surfaces later as `EACCES` when Next writes its cache.

#### libc parity

This image is **Alpine (musl)**, and the standalone bundle carries native packages —
`sharp`, `@next/swc`, `@swc` — whose prebuilt binaries are libc-specific. `npm` selects
them for the platform it installs *on*, so the build stage's base image decides what ends up
in `node_modules`.

`node-builder` and `node-runtime` are both Alpine, and both publish the same Node majors,
precisely so this lines up. If you substitute a **glibc** build stage (`node:22`,
`node:22-slim`, or any Debian/Ubuntu image), the result is a mismatch: `sharp` silently
degrades to its much slower WASM fallback, and native addons without a fallback fail to load
outright. Keep the build stage on Alpine, or run that app on a Debian-based runtime instead
of this image.

The same applies to the **Node major**: build and run on the same one. Because both images
now ship four majors, this is something you have to line up yourself — `docker-node-builder:node24`
pairs with `docker-node-runtime:node24`, and mixing them is the mistake to watch for:

```dockerfile
FROM ghcr.io/idbi/docker-node-builder:node24 AS build   # builds against Node 24 ABI
...
FROM ghcr.io/idbi/docker-node-runtime:node20            # runs on Node 20 — native addons break
```

Avoid `:latest` on either image for this reason: the two resolve independently, and a change
of default major would silently split the pair. Prefer an explicit `node<major>` tag on both
stages, or a single `ARG` if you template your Dockerfiles.

### Running with docker-compose

```yaml
services:
  web:
    image: your-registry/your-next-app:latest   # built FROM docker-node-runtime
    environment:
      NODE_ENV: production
      HEALTHCHECK_PATH: /api/health
    ports:
      - "80:3000"                                # host 80 -> container 3000 (non-root)
    restart: unless-stopped
```

### Kubernetes

```yaml
containers:
  - name: web
    image: your-registry/your-next-app:latest   # FROM docker-node-runtime
    ports:
      - { containerPort: 3000 }
    env:
      - { name: NODE_OPTIONS, value: "--max-old-space-size=384" }   # ~75% of the limit
    readinessProbe:
      httpGet: { path: /api/health, port: 3000 }
    resources:
      limits: { memory: 512Mi }
```

> Set `terminationGracePeriodSeconds` generously enough for in-flight SSR requests to
> finish; `dumb-init` ensures the `SIGTERM` actually reaches Node so the server drains.

---

## Configuration

Tune the runtime via environment variables (defaults shown).

| Variable                  | Default | Description |
| ------------------------- | ------- | ----------- |
| `NODE_ENV`                | `production` | Node/Next environment. Leave as `production` in deployed images |
| `PORT`                    | `3000` | Port the Next server listens on (also probed by the healthcheck) |
| `HOSTNAME`                | `0.0.0.0` | Bind address. Must stay `0.0.0.0` to be reachable from outside the container |
| `NEXT_TELEMETRY_DISABLED` | `1` | Disables Next.js telemetry collection |
| `HEALTHCHECK_PATH`        | `/` | Route the container `HEALTHCHECK` requests |
| `NODE_OPTIONS`            | *(unset)* | Node flags. Set `--max-old-space-size=<MB>` to ~75% of the container memory limit so V8 garbage-collects before the OOM killer fires |

`NODE_OPTIONS` is deliberately **not** set by default: a heap cap that does not match the
container's memory limit is worse than none. Set it per deployment alongside the limit.

Application-specific variables (`DATABASE_URL`, `NEXT_PUBLIC_*`, …) are passed at runtime as
usual. Note that `NEXT_PUBLIC_*` values are inlined **at build time** by Next, so setting
them here has no effect on the client bundle.

---

## Verifying the Image

```sh
# Runs as non-root
docker run --rm node-runtime:latest id                       # -> uid=1000(node) gid=1000(node)

# Node major matches the tag
docker run --rm --entrypoint node node-runtime:latest -v     # -> v22.x.y
docker image inspect node-runtime:latest \
    --format '{{index .Config.Labels "org.opencontainers.image.base.name"}}'
                                                             # -> docker.io/library/node:22-alpine

# dumb-init present and wired as the entrypoint
docker run --rm --entrypoint sh node-runtime:latest -c 'command -v dumb-init'

# The ISR/image cache dir exists and is writable by the runtime user
docker run --rm --entrypoint sh node-runtime:latest -c 'ls -ld /app/.next/cache'
                                                             # -> drwxr-xr-x node node
```

The image has no `server.js` of its own, so `docker run node-runtime:latest` exits
immediately with `Cannot find module '/app/server.js'` — that is expected. Verify the full
path with a downstream image built as in [Usage](#usage):

```sh
cid=$(docker run -d -p 3000:3000 your-next-app:latest)
sleep 15
docker inspect --format '{{.State.Health.Status}}' "$cid"    # -> healthy
curl -sI localhost:3000 | head -1                            # -> HTTP/1.1 200 OK
time docker stop "$cid"                                      # -> returns in ~1s, not 10s
docker rm "$cid"
```

A `docker stop` that takes the full 10-second timeout means `SIGTERM` is not reaching Node —
usually because a downstream image overrode `ENTRYPOINT` and dropped `dumb-init`.

---

## Troubleshooting

### Every asset returns `404` (unstyled page, missing JS)
`.next/static` and/or `public/` were not copied. The standalone output excludes them; add
both `COPY --from=build` lines from [Usage](#usage).

### `Cannot find module '/app/server.js'`
The standalone bundle was not copied to `/app`, or was copied into a subdirectory. The
`COPY --from=build /app/.next/standalone ./` destination must be the `WORKDIR` root.

### Container starts but is unreachable / connection refused
`HOSTNAME` was overridden to `localhost` or `127.0.0.1`. The Next standalone server binds
exactly what `HOSTNAME` says; it must be `0.0.0.0` inside a container. Also confirm the
published port matches `PORT`.

### `EACCES: permission denied` writing `.next/cache`
App files were copied as root. Use `COPY --chown=node:node` for every layer, or mount a
writable volume at `/app/.next/cache` for ISR-heavy apps.

### Healthcheck reports `unhealthy` but the app works
`HEALTHCHECK_PATH` (default `/`) returns a `4xx`/`5xx` — commonly because `/` requires
authentication. Point `HEALTHCHECK_PATH` at an unauthenticated health route.

### Container is `SIGKILL`ed on deploy / slow `docker stop`
A downstream image replaced `ENTRYPOINT` without `dumb-init`. Either keep the inherited
entrypoint or set `ENTRYPOINT ["dumb-init", "--"]` yourself.

### `Error loading shared library ld-linux-x86-64.so.2` from a native module
A prebuilt glibc binary that `libc6-compat` doesn't cover — almost always caused by
installing dependencies in a Debian image and copying them here. See
[libc parity](#libc-parity).

### `NODE_MODULE_VERSION` mismatch, or a native addon that fails only at runtime
The build stage and this image are on **different Node majors** — compiled addons are tied
to a major's ABI. Match the `node<major>` suffix on both images. See
[libc parity](#libc-parity).

### `next/image` optimization is unexpectedly slow
`sharp` fell back to its WASM build because the installed variant doesn't match musl. Check
with `docker run --rm <your-image> ls node_modules/@img/` — you want a
`sharp-linuxmusl-*` entry, not `sharp-linux-*` or only `sharp-wasm32`. See
[libc parity](#libc-parity).

---

## Image Information

- **Base Image**: `node:<major>-alpine`, built for majors **18, 20, 22, 24** (`:latest` = 22)
- **Exposed Port**: `3000` (HTTP)
- **User**: `node` (non-root, uid `1000`)
- **Init**: `dumb-init` as PID 1
- **Architectures**: `linux/amd64`
- **Version**: see [CHANGELOG.md](CHANGELOG.md) for release history

---

**Contact:** IDBI DevOps Team · [devops@idbi.pe](mailto:devops@idbi.pe)
