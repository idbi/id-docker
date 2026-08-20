# PHP 8.3 + Composer Docker Image

A production-ready Docker image based on **PHP 8.3 CLI** with a comprehensive set of pre-compiled extensions and **Composer** for dependency management. This image is designed for building, testing, and deploying modern PHP applications in containerized environments.

### What is php-builder?

`php-builder` provides a standardized, lightweight container for PHP development and CI/CD workflows. Unlike full-featured PHP images with web servers (Apache/Nginx), this CLI-focused image is optimized for running PHP scripts, CLI tools, and build processes. It comes pre-configured with commonly-needed extensions, eliminating the need to compile them yourself.

### Use Cases

- **Application builds**: Compile and package PHP applications
- **Composer dependency management**: Install and manage project dependencies
- **CI/CD pipelines**: Run automated testing, code analysis, and build steps
- **One-off PHP scripts**: Execute PHP utilities or maintenance scripts
- **Development environments**: Consistent development experience across teams

---

## Features

### Core PHP Installation
- **PHP 8.3 CLI**: The latest stable PHP 8.3 command-line interpreter
- **Composer** (latest): Dependency manager for PHP projects
- **Working directory**: `/app` - Pre-configured for your application code
- **Shell**: Bash for container interaction and scripting

### Pre-installed Extensions

#### **Database Extensions**
- **`pdo_mysql`**: PDO driver for MySQL/MariaDB connections with prepared statements
- **`pgsql`**: PostgreSQL driver for database operations
- **`sqlite3`**: SQLite 3 database support for lightweight, file-based databases

#### **Image Processing**
- **`gd`**: Powerful image manipulation library supporting:
  - PNG, JPEG, GIF formats
  - FreeType for true-type font rendering
  - WebP modern compression format
  - AVIF next-generation image format
  
#### **Text & Data Processing**
- **`mbstring`**: Multi-byte string handling for UTF-8 and international characters
- **`intl`**: Internationalization (i18n) and localization (l10n) support
- **`xml`**: XML parsing and generation
- **`xslt`**: XSLT stylesheet transformations

#### **Cryptography & Hashing**
- **`sodium`**: Modern cryptographic library (libsodium) for encryption, signing, and hashing
- **`bcmath`**: High-precision decimal arithmetic

#### **Utilities & System**
- **`zip`**: Create and extract ZIP archives
- **`curl`**: HTTP client for API calls and web requests
- **`soap`**: SOAP web services support
- **`gmp`**: Arbitrary precision arithmetic
- **`ldap`**: LDAP directory services for authentication
- **`pcntl`**: Process control for Unix signals and forking
- **`sockets`**: Low-level socket operations
- **`exif`**: EXIF metadata extraction from images

### Additional Tools
- **`unzip`**: Command-line utility for extracting ZIP files

---

## Usage

### **Pull from GitHub Container Registry**

Use the published image from GitHub Container Registry:

```sh
docker pull ghcr.io/idbi/docker-php-builder:latest
```

**Available tags:**
- `ghcr.io/idbi/docker-php-builder:latest` — Latest stable release
- `ghcr.io/idbi/docker-php-builder:X.Y.Z` — Specific version
- `ghcr.io/idbi/docker-php-builder:X` — Latest patch for major version

### **Build Locally**

Build from the local Dockerfile:

```sh
docker build -t php-builder:latest .
```

### **Run Composer Install**

Install project dependencies defined in `composer.json`:

```sh
docker run -it --rm -v $PWD:/app php-builder:latest composer install
```

Mount your local directory to `/app` and run Composer for dependency management.

### **Run PHP Scripts**

Execute a PHP script directly:

```sh
docker run -it --rm -v $PWD:/app php-builder:latest php script.php
```

Or with arguments:

```sh
docker run -it --rm -v $PWD:/app php-builder:latest php -d memory_limit=512M script.php
```

### **Run PHP CLI Tools**

Execute Composer binaries or PHP CLI tools:

```sh
docker run -it --rm -v $PWD:/app php-builder:latest ./vendor/bin/phpunit
docker run -it --rm -v $PWD:/app php-builder:latest ./vendor/bin/phpstan analyse
```

### **Interactive Development Shell**

Start an interactive bash shell for debugging or exploration:

```sh
docker run -it --rm -v $PWD:/app php-builder:latest bash
```

Inside the container, execute PHP commands directly:

```bash
$ php -v  # Check PHP version
$ composer show  # List installed packages
$ php -r "echo phpinfo();"  # Run inline PHP code
```

### **Environment Variables**

Pass environment variables to your PHP scripts:

```sh
docker run -it --rm \
  -v $PWD:/app \
  -e DB_HOST=localhost \
  -e DB_USER=root \
  -e APP_DEBUG=true \
  php-builder:latest php script.php
```

### **Working with Databases**

#### MySQL/MariaDB Connection

```sh
docker run -it --rm \
  -v $PWD:/app \
  --network host \
  php-builder:latest php -r "
    \$pdo = new PDO('mysql:host=localhost;dbname=testdb', 'root', 'password');
    \$result = \$pdo->query('SELECT VERSION()');
    echo \$result->fetch()[0];
  "
```

#### PostgreSQL Connection

```sh
docker run -it --rm \
  -v $PWD:/app \
  --network host \
  php-builder:latest php -r "
    \$conn = pg_connect('host=localhost dbname=testdb user=postgres');
    \$result = pg_query(\$conn, 'SELECT version()');
    echo pg_fetch_result(\$result, 0);
  "
```

### **Extending the Image**

Create your own Dockerfile that extends `php-builder`:

```dockerfile
FROM ghcr.io/idbi/php-builder:latest

# Copy your application code
COPY . /app

# Install dependencies
RUN composer install --no-dev --optimize-autoloader

# Set entrypoint to your PHP application
ENTRYPOINT ["php", "app.php"]
```

---

## Available PHP Extensions

Run the `php -m` command to list all available extensions:

```sh
docker run --rm php-builder:latest php -m
```

### Extension Categories

**Database Connectivity**: `pdo_mysql`, `pgsql`, `sqlite3`  
**Image & Media**: `gd` with support for multiple formats  
**Text & Encoding**: `mbstring`, `intl`, `xml`, `xslt`  
**Security & Crypto**: `sodium`, `bcmath`, `gmp`, `ldap`  
**HTTP & Network**: `curl`, `soap`, `sockets`  
**System Integration**: `pcntl`, `exif`, `zip`  

---

## Best Practices

### Volume Mounting
Always mount your application source as a volume for consistency:
```sh
docker run -it --rm -v $PWD:/app php-builder:latest ...
```

### Composer Caching
Cache Composer dependencies to speed up builds:
```sh
docker run -it --rm \
  -v $PWD:/app \
  -v composer-cache:/tmp/composer \
  -e COMPOSER_CACHE_DIR=/tmp/composer \
  php-builder:latest composer install
```

### Memory Management
For memory-intensive operations, increase the memory limit:
```sh
docker run -it --rm \
  -v $PWD:/app \
  php-builder:latest php -d memory_limit=1G script.php
```

### Production Deployments
In production, use immutable tags instead of `latest`:
```sh
docker pull ghcr.io/idbi/php-builder:v1.0.0-php-builder
```

---

## Performance Considerations

- **Image Size**: This image is optimized for production, with unused system packages removed
- **Startup Time**: CLI-focused design ensures fast container startup
- **Extension Compilation**: All extensions are pre-compiled, saving build time
- **Layer Caching**: Docker layer caching is leveraged to accelerate rebuilds

---

## Troubleshooting

### PHP Extension Not Loading

Verify an extension is compiled:
```sh
docker run --rm php-builder:latest php -i | grep <extension-name>
```

### Memory Exhaustion

Increase PHP memory limit:
```sh
docker run -it --rm -v $PWD:/app php-builder:latest \
  php -d memory_limit=2G script.php
```

### Composer Version Conflicts

Pin specific Composer version in your Dockerfile:
```dockerfile
FROM ghcr.io/idbi/php-builder:latest
RUN composer self-update 2.5.0
```

### Timezone Issues

Set the default timezone for PHP:
```sh
docker run -it --rm -v $PWD:/app php-builder:latest \
  php -d date.timezone=UTC script.php
```

---

## Image Information

- **Base Image**: `php:8.3-cli`
- **Size**: Optimized and minimal (see CHANGELOG for details)
- **Security**: Regular updates and patches applied
- **Architectures**: `linux/amd64`, `linux/arm64` (multi-arch manifest)
- **Version**: Check [CHANGELOG.md](CHANGELOG.md) for release history