# IDBI Docker Monorepo

This repository is the home for all **IDBI’s containerized automation tools and infrastructure components**. It uses a monorepo approach: each project or utility is placed in its own subdirectory, with a dedicated Docker build context.

---

## Components

### **php-builder**
A PHP 8.3 + Composer Docker image with comprehensive extensions for modern PHP applications. Includes support for databases (PDO MySQL, PostgreSQL), image processing (GD), and text processing (mbstring, intl, XML).

### **php-fpm**
A production-ready PHP 8.3 FPM (Alpine) runtime image tuned for Laravel. Ships hardened PHP settings, OPcache + JIT, a tuned FPM pool, a FastCGI healthcheck, and runs non-root. Pairs with `php-builder` (build) — apps extend it via `FROM` and run behind a separate nginx container.

### **php-nginx**
A production-ready nginx (Alpine) front end for the `php-fpm` runtime. Serves a Laravel app's static assets from `/app/public` and reverse-proxies PHP requests to a separate php-fpm container over FastCGI. Ships gzip, static-asset caching, security headers, and an internal healthcheck; runs non-root on port 8080.

### **node-builder**
A Node.js 22 (Alpine) + OpenJDK 17 build image for applications requiring both Node.js and Java. Ships a full `node-gyp` toolchain, `git`, and `rsync` for multi-language CI/CD workflows. Pairs with `node-runtime` (runtime) — both share the same Alpine base and Node major so build artifacts are binary compatible.

### **node-runtime**
A production-ready Node.js 22 (Alpine) runtime image tuned for Next.js apps built with `output: 'standalone'`. Ships `dumb-init` for graceful shutdown, an HTTP healthcheck, and runs non-root on port 3000. Pairs with `node-builder` (build) — apps extend it via `FROM` and need no web-server sidecar.

### **certbot-renewal**
An automated TLS/SSL certificate renewal solution using Certbot with DNS-01 validation (AWS Route53) and secure upload to HashiCorp Vault. Designed for Kubernetes CronJobs and standalone automation.

### **ssh-agent**
A minimal Debian 12 slim image with `openssh-client`, `rsync`, `git`, and `curl`, running as an unprivileged `deploy` user. Used for key-based remote deployment and file-transfer steps in CI/CD pipelines.

---

## Repository Structure

```
docker/
├── php-builder/
│   ├── Dockerfile
│   ├── README.md
│   └── CHANGELOG.md
├── php-fpm/
│   ├── Dockerfile
│   ├── README.md
│   ├── CHANGELOG.md
│   └── docker/
├── php-nginx/
│   ├── Dockerfile
│   ├── README.md
│   ├── CHANGELOG.md
│   └── docker/
├── node-builder/
│   ├── Dockerfile
│   ├── README.md
│   └── CHANGELOG.md
├── node-runtime/
│   ├── Dockerfile
│   ├── README.md
│   ├── CHANGELOG.md
│   └── docker/
├── ssh-agent/
│   ├── Dockerfile
│   ├── README.md
│   └── CHANGELOG.md
├── certbot-renewal/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── README.md
│   ├── manifests/
│   └── scripts/
├── traefik/                      # deployment config only — no image is built
│   └── docker-compose.yml
├── .github/
│   ├── scripts/
│   │   └── validate-releases.sh  # derives the build matrix from released tags
│   └── workflows/
│       ├── docker-publish.yml
│       └── release-please.yml
├── release-please-config.json    # component registry (see "Add a New Project")
├── .release-please-manifest.json # current version per component
└── README.md
```

---

## Philosophy

- **Component Independence:**  
  Every project is self-contained and portable as a Docker build context.

- **Unified Automation:**  
  A common CI/CD workflow discovers, builds, and (optionally) publishes every project’s image.

- **Extensibility:**  
  To add a tool, simply create a new directory with a `Dockerfile` and any supporting scripts/configuration.

---

## Usage Example

```sh
# Build any project
cd <project-directory>
docker build -t <project-name>:latest .

# Run, passing required configuration via environment variables as needed
docker run --rm -e VAR1=value1 -e VAR2=value2 <project-name>:latest
```

_Refer to individual project documentation or code for runtime requirements and configuration options._

---

## Deployment & Versioning

This repository uses [Release Please](https://github.com/googleapis/release-please) to automate versioning and Docker image releases.

### How It Works

1. **Automated Release PRs**: Release Please monitors commits and automatically creates a pull request when changes are detected.
2. **Semantic Versioning**: Each component follows semantic versioning (Major.Minor.Patch).
3. **Component Tags**: Git tags include both the component name and version, in the form `<component>@v<version>` (e.g., `php-builder@v1.2.3`).
4. **Single Release PR**: All changed components are included in a single pull request for review.
5. **Merged Changelog**: Merging the release PR automatically publishes new image versions.

### Image Naming

Images are published to [GitHub Container Registry (GHCR)](https://ghcr.io) with the following pattern:
```
ghcr.io/idbi/docker-<component>:<version>
```

Each release publishes three tags for the component — the exact version, the major version, and `latest`:
- `ghcr.io/idbi/docker-php-fpm:1.0.3` — Specific version
- `ghcr.io/idbi/docker-php-fpm:1` — Latest patch for a major version
- `ghcr.io/idbi/docker-php-fpm:latest` — Latest stable release

All images are built for `linux/amd64` only, with build provenance and an SBOM attached and attested to the registry.

### Triggering a Release

Simply merge your changes to the main branch. Release Please will automatically:
1. Detect changes
2. Create a release PR with updated versions
3. Build and publish Docker images when the release PR is merged

---

## How to Add a New Project

1. **Create the component directory** — `<component>/Dockerfile`, plus a `docker/` subdirectory for any runtime config the Dockerfile copies in. The build context is the component directory itself, so every `COPY` path must be relative to it (`COPY docker/php.ini …`, not `COPY php-fpm/docker/php.ini …`).
2. **Add a `README.md`** with usage notes, a configuration table, and verification commands. Use `php-fpm/README.md` or `node-runtime/README.md` as the template.
3. **Register the component in `release-please-config.json`** under `packages`, using the directory name for both the key and `component`:
   ```json
   "my-component": {
     "component": "my-component",
     "release-type": "simple"
   }
   ```
   This step is **required** — the publish pipeline discovers components from released tags, so an unregistered directory is never built. Leave `.release-please-manifest.json` alone; Release Please adds the entry itself on the first release.
4. **Add a `CHANGELOG.md`** containing just `# Changelog`. Release Please rewrites it on each release.
5. **Merge to `main`** with a `feat(<component>):` commit. Release Please opens a release PR; merging it creates the `<component>@vX.Y.Z` tag, which is what triggers the image build and push. No image is published before that tag exists.

---

## Contributing

- Suggestions, bugfixes, and new tools are welcome via pull requests or issues.
- Please use meaningful, unique directory names for each new project.


---

**Contact:**  
IDBI DevOps Team · [devops@idbi.pe](mailto:devops@idbi.pe)