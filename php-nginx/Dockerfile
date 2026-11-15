# Production-ready nginx front end for the php-fpm runtime image.
#
# Serves a Laravel app's static assets from /app/public and forwards PHP
# requests to a SEPARATE php-fpm container over FastCGI (port 9000). This image
# carries NO application code: bake your app's `public/` in via a downstream
# COPY, or share it with the php-fpm container through a volume.
#
# Runs fully non-root (the `nginx` user) on port 8080, so it works under
# restricted Kubernetes Pod Security policies without extra privileges.

FROM nginx:1.31.8-alpine3.24

# Main tuning config + the Laravel server block template. The template is
# rendered to /etc/nginx/conf.d/default.conf at container start by the base
# image's entrypoint (envsubst over the NGINX_* env vars); nginx's own runtime
# variables ($uri, $fastcgi_script_name, ...) are left untouched because they
# are not defined as environment variables.
COPY docker/nginx.conf            /etc/nginx/nginx.conf
COPY docker/default.conf.template /etc/nginx/templates/default.conf.template

# Runtime-tunable knobs consumed by the template. Override at runtime
# (docker `-e` / Kubernetes env) to point at your php-fpm service, change the
# document root, upload cap, or FastCGI timeout. NGINX_CLIENT_MAX_BODY_SIZE
# mirrors the php-fpm image's upload limits (php.ini upload_max_filesize=64M).
ENV NGINX_PORT=8080 \
    NGINX_ROOT=/app/public \
    NGINX_PHP_FPM_HOST=weapp \
    NGINX_PHP_FPM_PORT=9000 \
    NGINX_CLIENT_MAX_BODY_SIZE=64m \
    NGINX_FASTCGI_READ_TIMEOUT=60s

# Make the paths nginx writes to at runtime owned by the unprivileged user, and
# pre-create the writable temp dirs referenced in nginx.conf. /etc/nginx/conf.d
# must be writable so the base entrypoint's envsubst step can render the
# template as the `nginx` user; /var/log/nginx already symlinks access/error
# logs to the container's stdout/stderr.
RUN mkdir -p /tmp/nginx-client /tmp/nginx-proxy /tmp/nginx-fastcgi \
             /tmp/nginx-uwsgi /tmp/nginx-scgi \
    && chown -R nginx:nginx /var/cache/nginx /var/log/nginx \
             /etc/nginx/conf.d /tmp/nginx-client /tmp/nginx-proxy \
             /tmp/nginx-fastcgi /tmp/nginx-uwsgi /tmp/nginx-scgi

USER nginx

EXPOSE 8080

# Assert the internal /readyz endpoint returns HTTP 200 — not merely that a
# response came back. busybox wget's -S prints the status line (even with -q),
# which we match explicitly, so a 3xx/4xx/5xx or an unreachable server all fail
# the check. ${NGINX_PORT} is expanded at runtime by the shell, so the check
# follows the configured listen port even when it is overridden with -e.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -S -q -T 2 -O /dev/null "http://127.0.0.1:${NGINX_PORT}/readyz" 2>&1 \
        | grep -qE 'HTTP/[0-9.]+ 200' || exit 1

# The base image's entrypoint renders templates from /etc/nginx/templates,
# then execs this command.
CMD ["nginx", "-g", "daemon off;"]
