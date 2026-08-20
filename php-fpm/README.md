# PHP-FPM Runtime Image for Laravel

A production-ready Docker image based on **PHP 8.3 FPM (Alpine)**, tuned specifically for serving
**Laravel** applications. It ships a hardened PHP configuration, an OPcache + JIT setup for
deployed (immutable) code, a tuned FPM process pool, a FastCGI healthcheck, and runs as a
non-root user out of the box.

### What is php-fpm?

`php-fpm` is the **runtime** counterpart to [`php-builder`](../php-builder). Where `php-builder`
is a CLI + Composer image used to *build* an application (install dependencies, compile assets),
`php-fpm` is a lean, FPM-only image used to *run* it.

This image deliberately carries **no application code**. You build your Laravel app elsewhere and
`COPY` the result into a stage based on this image (see [Usage](#usage)). It exposes PHP-FPM on
TCP port **9000** and expects a web server (typically **nginx**) to run as a **separate
container or pod** — one process per container.

### Use Cases

- **Production Laravel web tier**: Serve HTTP requests behind nginx in Docker/Kubernetes.
- **Queue workers & scheduler**: The same image runs `php artisan queue:work`, Horizon, or
  `schedule:work` (the `pcntl` and `posix` extensions are included).
- **Consistent runtime base**: A single, audited base image that all your Laravel services
  extend via `FROM`.

---

## Features

### Core Runtime
- **PHP 8.3 FPM** on **Alpine** — small image, fast cold starts.
- **Non-root**: runs as the `www-data` user.
- **Listens on** TCP **`9000`** for nginx (or any FastCGI client).
- **Working directory**: `/app`.
- **Worker output** (FPM error logs, stdout/stderr) goes to the container logs; PHP's own
  `error_log` writes to `/var/log/php-fpm/errors.log` (see [Logging](#logging)). FPM's
  **per-request access log is disabled** by default (nginx already logs requests).

### Production Tuning (`conf.d/zz-laravel.ini`)
- **OPcache** sized for large codebases: `memory_consumption=512`, `interned_strings_buffer=128`,
  `max_accelerated_files=60000`, with a secondary file cache at `/tmp/php-opcache`.
- **`validate_timestamps=0`** — deployed code is never re-stat'd; invalidate by rolling a new
  image / restarting FPM.
- **JIT** (`opcache.jit=1255`, 128 MB buffer) for CPU-bound workloads.
- **Hardened**: `expose_php=Off`, `display_errors=Off`, and an **`open_basedir`** jail limiting
  filesystem access to the app tree + `/tmp` (see [open_basedir](#open_basedir)).
- `memory_limit=512M`, `max_execution_time=60`, upload limits (64M / 65M post), enlarged
  `realpath_cache`, `max_input_vars=5000`, `UTF-8` default charset, `UTC` timezone.

### FPM Pool (`php-fpm.d/zz-www.conf`)
- `pm = dynamic` with worker counts overridable via environment variables (see
  [Configuration](#configuration)).
- `clear_env = no` so container environment variables reach your app.
- `/ping` and `/status` endpoints enabled; worker output forwarded to container logs.

### Healthcheck
- A `HEALTHCHECK` runs `php-fpm-healthcheck`, which pings the FPM `/ping` endpoint over FastCGI
  using `cgi-fcgi`.

### Pre-installed Extensions

| Category        | Extensions |
| --------------- | ---------- |
| **Performance** | `opcache` (with JIT) |
| **Database**    | `pdo_mysql`, `mysqli`, `pdo_pgsql` |
| **Cache/Queue** | `redis` (PECL) |
| **Laravel core**| `mbstring`, `bcmath`, `pcntl`, `sockets`, `ctype`, `tokenizer`, `openssl` |
| **Image/Media** | `gd`, `exif` |
| **Text/Intl**   | `intl`, `soap`, `xml` |
| **Crypto/Math** | `sodium`, `gmp` |
| **Utilities**   | `zip`, `ldap` |

> Run `docker run --rm ghcr.io/idbi/docker-php-fpm:latest php -m` to list everything available.

---

## Usage

### Pull from GitHub Container Registry

```sh
docker pull ghcr.io/idbi/docker-php-fpm:latest
```

**Available tags:**
- `ghcr.io/idbi/docker-php-fpm:latest` — Latest stable release
- `ghcr.io/idbi/docker-php-fpm:X.Y.Z` — Specific version
- `ghcr.io/idbi/docker-php-fpm:X` — Latest patch for a major version

### Build Locally

```sh
docker build -t php-fpm:latest ./php-fpm
```

### Recommended: multi-stage build for your Laravel app

Use `php-builder` to install dependencies and compile assets, then copy the artifacts onto this
runtime image. This keeps Composer, Node, and build caches out of the final image.

```dockerfile
# syntax=docker/dockerfile:1

# --- Stage 1: PHP dependencies ---
FROM ghcr.io/idbi/docker-php-builder:latest AS vendor
WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-scripts --no-autoloader --prefer-dist

# --- Stage 2: front-end assets (optional) ---
FROM ghcr.io/idbi/docker-node-builder:latest AS assets
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# --- Stage 3: runtime ---
FROM ghcr.io/idbi/docker-php-fpm:latest

# Copy the application code, then layer in the built artifacts.
COPY --chown=www-data:www-data . /app
COPY --chown=www-data:www-data --from=vendor /app/vendor ./vendor
COPY --chown=www-data:www-data --from=assets /app/public/build ./public/build

# Optimize the autoloader and cache Laravel config/routes/views into the image.
USER root
RUN composer dump-autoload --no-dev --optimize 2>/dev/null || true
USER www-data
RUN php artisan config:cache \
    && php artisan route:cache \
    && php artisan view:cache
```

> **OPcache note:** Because `opcache.validate_timestamps=0`, code changes only take effect when a
> new image is deployed (or FPM is restarted). This is intentional for production immutability.

### Running with nginx (docker-compose)

Nginx and PHP-FPM run as separate services; nginx forwards `.php` requests to `app:9000`.

```yaml
services:
  app:
    image: your-registry/your-laravel-app:latest   # built FROM docker-php-fpm
    environment:
      APP_ENV: production
      APP_KEY: ${APP_KEY}
      DB_HOST: mysql
      PHP_FPM_PM_MAX_CHILDREN: "40"
    healthcheck:
      test: ["CMD", "php-fpm-healthcheck"]
    restart: unless-stopped

  web:
    image: nginx:alpine
    depends_on: [app]
    ports:
      - "80:80"
    volumes:
      - ./docker/nginx.conf:/etc/nginx/conf.d/default.conf:ro
```

A minimal matching nginx server block:

```nginx
server {
    listen 80;
    root /app/public;
    index index.php;

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \.php$ {
        include fastcgi_params;
        fastcgi_pass app:9000;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    }
}
```

> Nginx needs read access to your app's `public/` directory. In a split-container setup, either
> bake the static assets into the nginx image too, or share them via a named volume.

### Queue workers & scheduler

The same image runs Laravel's background processes — just override the command:

```sh
# Queue worker
docker run --rm your-laravel-app:latest php artisan queue:work --tries=3

# Scheduler (long-running)
docker run --rm your-laravel-app:latest php artisan schedule:work
```

---

## Configuration

Tune the FPM process manager at runtime via environment variables (defaults shown):

| Variable                       | Default | Description |
| ------------------------------ | ------- | ----------- |
| `PHP_FPM_PM_MAX_CHILDREN`      | `20`    | Max concurrent FPM worker processes |
| `PHP_FPM_PM_START_SERVERS`     | `4`     | Workers started on boot |
| `PHP_FPM_PM_MIN_SPARE_SERVERS` | `2`     | Minimum idle workers |
| `PHP_FPM_PM_MAX_SPARE_SERVERS` | `6`     | Maximum idle workers |
| `FPM_HEALTHCHECK_ADDR`         | `127.0.0.1:9000` | Address the healthcheck pings |

Rule of thumb for `pm.max_children`: `(container memory) / (avg PHP process size, ~30–50MB)`.

To override PHP settings (e.g. a bigger `memory_limit`), drop an extra `.ini` into
`$PHP_INI_DIR/conf.d/` in your downstream image — files load alphabetically, so use a name after
`zz-laravel.ini` to win.

### open_basedir

For defense-in-depth, PHP filesystem access is jailed to:

```
/app:/app/vendor:/app/storage:/app/bootstrap:/tmp:/dev/null
```

If your app reads or writes outside these paths (e.g. a shared mount, a different storage path),
**extend the list** — `open_basedir` is not additive, so re-declare the full path set in a
later-loading `.ini`:

```ini
; conf.d/zzz-app.ini
open_basedir = /app:/app/vendor:/app/storage:/app/bootstrap:/tmp:/dev/null:/mnt/shared
```

### Logging

PHP's `error_log` writes to `/var/log/php-fpm/errors.log` (a directory pre-created and owned by
`www-data`). There is **no logrotate inside the container**, so on long-running pods either mount
that path to a host/volume with rotation, or — for stdout-based aggregation (Docker/Kubernetes) —
point it at stderr in a downstream `.ini`:

```ini
; conf.d/zzz-app.ini
error_log = /dev/stderr
```

FPM is configured to emit **errors only**. `zz-www.conf` sets `log_level = error`, which drops
the FPM master's `notice`-level chatter (the "ready to handle connections" boot line and the
`pm = dynamic` "seems busy"/"reached pm.max_children" warnings); raise it back to `warn`/`notice`
if you want those capacity signals. The **per-request access log is disabled** by pointing it at
`/dev/null` — an *explicit* override is required because the base image's `docker.conf` sets
`access.log = /proc/self/fd/2`, so commenting the directive out is not enough. To re-enable it,
set `access.log = /proc/self/fd/2` in a later-loading pool config. Genuine PHP errors and worker
output still reach the logs via `error_log` and `catch_workers_output`.

---

## Verifying the Image

```sh
# Extensions
docker run --rm php-fpm:latest php -m

# Production settings applied
docker run --rm php-fpm:latest php -i | grep -E 'opcache.enable|validate_timestamps|expose_php'

# Runs as non-root
docker run --rm php-fpm:latest id            # -> www-data

# FPM config is valid
docker run --rm php-fpm:latest php-fpm -t    # -> "test is successful"
```

---

## Troubleshooting

### Code changes don't show up
Expected — `opcache.validate_timestamps=0` means deployed code is cached until FPM restarts. Roll
a new image, restart the container, or run `php artisan opcache:clear` (with a package like
`appstract/laravel-opcache`).

### `502 Bad Gateway` from nginx
Nginx can't reach FPM. Confirm both share a network and `fastcgi_pass` points at `app:9000`.
Check the app container is `healthy` (`docker inspect --format '{{.State.Health.Status}}' <id>`).

### `Permission denied` writing to `storage/` or `bootstrap/cache`
The container runs as `www-data`. Ensure you `COPY --chown=www-data:www-data` your app, or fix
ownership in your downstream Dockerfile.

### Environment variables not visible in PHP
The pool sets `clear_env = no`, so they should be. Confirm you cached config *after* the variables
were available, or avoid `config:cache` in environments where env changes at runtime.

### `open_basedir restriction in effect` errors
Your app touched a path outside the jail. Add the path to `open_basedir` in a later-loading `.ini`
(see [open_basedir](#open_basedir)). Common culprits: a custom storage/log path, a mounted shared
volume, or a system temp dir other than `/tmp`.

---

## Image Information

- **Base Image**: `php:8.3-fpm-alpine`
- **Exposed Port**: `9000` (FastCGI)
- **User**: `www-data` (non-root)
- **Architectures**: `linux/amd64`, `linux/arm64` (multi-arch manifest)
- **Version**: see [CHANGELOG.md](CHANGELOG.md) for release history

---

**Contact:** IDBI DevOps Team · [devops@idbi.pe](mailto:devops@idbi.pe)
