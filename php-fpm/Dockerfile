# Production-ready PHP-FPM runtime base for Laravel applications.
#
# This image carries NO application code. Build your app with `php-builder`
# (composer install, asset compilation) and then `COPY` the artifacts into a
# stage based on this image. Nginx is expected to run as a separate container
# that talks to PHP-FPM over TCP port 9000.

FROM php:8.3.36-fpm-alpine3.24

# `install-php-extensions` resolves the Alpine/musl build + runtime deps for
# each extension automatically, so we don't have to track apk-dev packages by
# hand.
COPY --from=ghcr.io/mlocati/php-extension-installer:2.13.2 /usr/bin/install-php-extensions /usr/local/bin/

# `fcgi` provides cgi-fcgi, used by the HEALTHCHECK to ping the FPM pool.
RUN apk add --no-cache fcgi \
    && install-php-extensions \
        opcache \
        pdo_mysql \
        pdo_pgsql \
        mysqli \
        gd \
        intl \
        zip \
        bcmath \
        pcntl \
        sockets \
        exif \
        soap \
        gmp \
        ldap \
        mbstring \
        sodium \
        redis \
    && rm -rf /usr/local/bin/install-php-extensions

# Production PHP + opcache settings and the tuned FPM pool. The `zz-` prefix
# ensures these load last and override the image defaults.
COPY docker/php.ini            "$PHP_INI_DIR/conf.d/zz-laravel.ini"
COPY docker/www.conf           /usr/local/etc/php-fpm.d/zz-www.conf
COPY docker/php-fpm-healthcheck /usr/local/bin/php-fpm-healthcheck
RUN chmod +x /usr/local/bin/php-fpm-healthcheck

# Defaults for the pm.* knobs referenced in zz-www.conf. Override at runtime
# (docker `-e` / Kubernetes env) to match the container's CPU/memory budget.
ENV PHP_FPM_PM_MAX_CHILDREN=20 \
    PHP_FPM_PM_START_SERVERS=4 \
    PHP_FPM_PM_MIN_SPARE_SERVERS=2 \
    PHP_FPM_PM_MAX_SPARE_SERVERS=6

WORKDIR /app

# Laravel needs these writable at runtime. They are created here so the image
# is sane even before an app COPYs its own tree on top; `chown` keeps them
# owned by the unprivileged runtime user. We also pre-create the PHP error-log
# directory (error_log in php.ini) and the OPcache secondary file-cache dir,
# both owned by www-data so the non-root process can write to them.
RUN mkdir -p storage/framework/cache storage/framework/sessions \
             storage/framework/views storage/logs bootstrap/cache \
             /var/log/php-fpm /tmp/php-opcache \
    && chown -R www-data:www-data /app /var/log/php-fpm /tmp/php-opcache

# Run FPM as the unprivileged user shipped with the base image.
USER www-data

EXPOSE 9000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD ["php-fpm-healthcheck"]

CMD ["php-fpm"]
