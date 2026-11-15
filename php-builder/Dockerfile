# Pinned PHP 8.3 patch release
FROM php:8.3.36-cli

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpng-dev \
    libjpeg-dev \
    libfreetype6-dev \
    libzip-dev \
    libonig-dev \
    libxml2-dev \
    libxslt-dev \
    libwebp-dev \
    libavif-dev \
    libgmp-dev \
    libldap2-dev \
    libpq-dev \
    libsqlite3-dev \
    libcurl4-openssl-dev \
    libicu-dev \
    libsodium-dev \
    unzip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install basic PHP extensions
RUN docker-php-ext-install pdo_mysql curl gd mbstring bcmath intl zip soap pcntl sockets exif sodium

# Install Composer (pinned version from the official image)
COPY --from=composer:2.11.2 /usr/bin/composer /usr/local/bin/composer
RUN composer --version

# Set the working directory
WORKDIR /app

# Start with bash shell on container run
# Build/CI image: runs as root on purpose so mounted workspaces and CI caches stay
# writable. Runtime images drop privileges.
# nosemgrep: dockerfile.security.missing-user.missing-user
CMD ["bash"]
