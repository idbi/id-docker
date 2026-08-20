# Nginx Front End for Laravel (php-fpm)

A production-ready Docker image based on the **latest nginx (Alpine)**, tuned to serve
**Laravel** applications that run on the companion [`php-fpm`](../php-fpm) image. It ships a
hardened nginx configuration, gzip compression, long-lived static-asset caching, security
headers, an internal healthcheck endpoint, and runs as a **non-root** user on port **8080**
out of the box.

### What is php-nginx?

`php-nginx` is the **web/front-end** counterpart to [`php-fpm`](../php-fpm). The `php-fpm`
image is a lean, FPM-only runtime that deliberately expects a web server to run as a
**separate container or pod** and talk to it over FastCGI on TCP **9000**. `php-nginx` is
that web server: it serves the app's static files from `public/` and forwards every `.php`
request to the php-fpm container.

This image deliberately carries **no application code**. You either bake your app's
`public/` directory into a downstream image (`FROM ghcr.io/idbi/docker-php-nginx`) or share
it with the php-fpm container through a volume (see [Usage](#usage)).

### Use Cases

- **Production Laravel web tier**: Terminate HTTP and reverse-proxy PHP to php-fpm in
  Docker or Kubernetes — one process per container.
- **Static asset serving**: Serve compiled CSS/JS/images with immutable, far-future cache
  headers and gzip, offloading php-fpm.
- **Consistent front end**: A single, audited nginx base that every Laravel service pairs
  with its php-fpm runtime.

---

## Features

### Core
- **Latest nginx** on **Alpine** — small image, fast cold starts.
- **Non-root**: runs as the `nginx` user on port **`8080`**, so it works under restricted
  Kubernetes Pod Security policies without extra privileges.
- **Document root**: `/app/public` (overridable).
- **Access/error logs** go to the container's stdout/stderr.

### Production Tuning (`nginx.conf`)
- `sendfile`, `tcp_nopush`, `tcp_nodelay`, `keepalive_timeout 65`, enlarged
  `worker_connections` and `types_hash_max_size`.
- **gzip** enabled for text, JSON, JS/CSS, SVG, XML and wasm.
- **`server_tokens off`** — the nginx version is not leaked in headers or error pages.
- Extended access-log format including upstream/request timings for FPM latency debugging.
- All temp/pid paths point at writable locations for clean non-root operation.

### Laravel Server Block (`conf.d/default.conf`)
- Front controller routing: `try_files $uri $uri/ /index.php?$query_string`.
- FastCGI proxy to php-fpm with sane buffers, `fastcgi_read_timeout`, and
  `X-Powered-By` hidden. Upstream host/port are configurable via environment variables.
- **Static-asset caching**: `expires 1y; Cache-Control "public, immutable"` with access
  logging off.
- **Security headers**: `X-Frame-Options`, `X-Content-Type-Options: nosniff`,
  `X-XSS-Protection`, `Referrer-Policy`.
- **Hardening**: denies dotfiles (except `/.well-known/`) and `.env` / `.log` / `.lock`
  files.

### Healthcheck
- A `HEALTHCHECK` requests the internal `GET /readyz` endpoint and **asserts an HTTP `200`
  status** (not merely that a response came back), so a `3xx`/`4xx`/`5xx` or an unreachable
  server all mark the container unhealthy. `/readyz` is answered by nginx directly (no
  php-fpm dependency), so it reports a deterministic `200` even before app code is deployed.
  The check follows `NGINX_PORT`, so it keeps working when the listen port is overridden.

> The server block is rendered at container start from a template via `envsubst`, so the
> upstream, document root, and limits are set from environment variables — no rebuild
> needed to retarget the php-fpm service.

---

## Usage

### Pull from GitHub Container Registry

```sh
docker pull ghcr.io/idbi/docker-php-nginx:latest
```

**Available tags:**
- `ghcr.io/idbi/docker-php-nginx:latest` — Latest stable release
- `ghcr.io/idbi/docker-php-nginx:X.Y.Z` — Specific version
- `ghcr.io/idbi/docker-php-nginx:X` — Latest patch for a major version

### Build Locally

```sh
docker build -t php-nginx:latest ./php-nginx
```

### Running with php-fpm (docker-compose)

Nginx and PHP-FPM run as separate services; nginx forwards `.php` requests to `app:9000`.
Both containers need to see the app's `public/` directory — here it is shared via a named
volume seeded by the app image.

```yaml
services:
  app:
    image: your-registry/your-laravel-app:latest   # built FROM docker-php-fpm
    environment:
      APP_ENV: production
      APP_KEY: ${APP_KEY}
      DB_HOST: mysql
    volumes:
      - app-public:/app/public
    healthcheck:
      test: ["CMD", "php-fpm-healthcheck"]
    restart: unless-stopped

  web:
    image: ghcr.io/idbi/docker-php-nginx:latest
    depends_on: [app]
    environment:
      NGINX_PHP_FPM_HOST: app          # service name of the php-fpm container
      NGINX_PHP_FPM_PORT: "9000"
    volumes:
      - app-public:/app/public:ro
    ports:
      - "80:8080"                       # host 80 -> container 8080 (non-root)
    restart: unless-stopped

volumes:
  app-public:
```

> In a split-container setup nginx needs read access to the same `public/` tree php-fpm
> serves so `SCRIPT_FILENAME` resolves. Share it via a volume as above, or bake the assets
> into the nginx image (next section).

### Recommended: bake `public/` into the image

For immutable deploys, copy the app's built `public/` (compiled assets included) straight
into the nginx image so it is self-contained — no shared volume required.

```dockerfile
# syntax=docker/dockerfile:1
FROM ghcr.io/idbi/docker-php-nginx:latest

# Copy only what nginx serves: the public web root (index.php + built assets).
COPY --chown=nginx:nginx public/ /app/public/
```

Build your Laravel assets first (e.g. with `php-builder` / `node-builder`), then this image
serves them while php-fpm executes the PHP.

### Kubernetes (two containers, one pod)

Run `php-nginx` and `php-fpm` as containers in the same pod so nginx reaches FPM on
`127.0.0.1:9000`, sharing `public/` through an `emptyDir` populated by the app image:

```yaml
containers:
  - name: app
    image: your-registry/your-laravel-app:latest   # FROM docker-php-fpm
    volumeMounts:
      - { name: public, mountPath: /app/public }
  - name: web
    image: ghcr.io/idbi/docker-php-nginx:latest
    env:
      - { name: NGINX_PHP_FPM_HOST, value: "127.0.0.1" }
    ports:
      - { containerPort: 8080 }
    volumeMounts:
      - { name: public, mountPath: /app/public, readOnly: true }
volumes:
  - { name: public, emptyDir: {} }
```

---

## Configuration

Tune the server block at runtime via environment variables (defaults shown). They are
substituted into the config when the container starts.

| Variable                     | Default        | Description |
| ---------------------------- | -------------- | ----------- |
| `NGINX_PORT`                 | `8080`         | Port nginx listens on (non-privileged) |
| `NGINX_ROOT`                 | `/app/public`  | Document root served by nginx |
| `NGINX_PHP_FPM_HOST`         | `app`          | Hostname of the php-fpm container/service |
| `NGINX_PHP_FPM_PORT`         | `9000`         | FastCGI port on the php-fpm container |
| `NGINX_CLIENT_MAX_BODY_SIZE` | `64m`          | Max request/upload size (match php-fpm's `upload_max_filesize`) |
| `NGINX_FASTCGI_READ_TIMEOUT` | `60s`          | How long nginx waits for a php-fpm response |

To add or override nginx directives beyond these, mount or `COPY` an extra `*.conf` into
`/etc/nginx/conf.d/` in a downstream image, or replace `/etc/nginx/nginx.conf` entirely.

> Keep `NGINX_CLIENT_MAX_BODY_SIZE` aligned with the php-fpm image's `post_max_size` /
> `upload_max_filesize` (64M / 65M by default) so nginx doesn't reject uploads PHP would
> have accepted, or vice versa.

---

## Verifying the Image

```sh
# Config parses (nginx validates it at build/run time too)
docker run --rm php-nginx:latest nginx -t          # -> "test is successful"

# Runs as non-root
docker run --rm php-nginx:latest id                # -> uid=101(nginx)

# Run it (NGINX_PHP_FPM_HOST must resolve at startup so nginx can bind its
# FastCGI upstream; point it at loopback just to boot without a real backend).
cid=$(docker run -d -e NGINX_PHP_FPM_HOST=127.0.0.1 -p 8080:8080 php-nginx:latest)

# Template rendered with your overrides
docker exec "$cid" grep -E "fastcgi_pass|listen " /etc/nginx/conf.d/default.conf

# Healthcheck: /readyz returns an explicit HTTP 200 (answered by nginx, no
# backend needed), and the container reports healthy.
docker exec "$cid" wget -S -q -O /dev/null http://127.0.0.1:8080/readyz 2>&1 | head -1
                                                       # -> HTTP/1.1 200 OK
docker inspect --format '{{.State.Health.Status}}' "$cid"   # -> healthy
docker rm -f "$cid"
```

---

## Troubleshooting

### `502 Bad Gateway`
Nginx can't reach php-fpm. Confirm both share a network/pod and that `NGINX_PHP_FPM_HOST` /
`NGINX_PHP_FPM_PORT` point at the FPM container (`app:9000` by default). Check the php-fpm
container is `healthy`.

### `404 Not Found` for every route, or assets missing
Nginx can't see the app's `public/` directory. Ensure `NGINX_ROOT` points at a `public/`
that contains `index.php`, and that it is either baked into this image or shared with the
php-fpm container via the same volume/mount.

### `File not found` from PHP (blank page / FPM 404)
`SCRIPT_FILENAME` resolved to a path php-fpm can't read. In a split-container setup, nginx
and php-fpm must see the **same** `public/` at the **same** path (`/app/public`). Share it
via one volume rather than copying into only one side.

### Uploads rejected with `413 Request Entity Too Large`
Raise `NGINX_CLIENT_MAX_BODY_SIZE` (and the php-fpm `post_max_size` / `upload_max_filesize`
to match).

### `Permission denied` on startup
The container runs as `nginx` (uid 101). If you mount your own config or web root, make it
readable by that user (e.g. `COPY --chown=nginx:nginx`).

---

## Image Information

- **Base Image**: `nginx:alpine`
- **Exposed Port**: `8080` (HTTP)
- **User**: `nginx` (non-root)
- **Architectures**: `linux/amd64`, `linux/arm64` (multi-arch manifest)
- **Version**: see [CHANGELOG.md](CHANGELOG.md) for release history

---

**Contact:** IDBI DevOps Team · [devops@idbi.pe](mailto:devops@idbi.pe)
