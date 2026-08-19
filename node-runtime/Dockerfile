# Production-ready Node.js runtime for Next.js applications.
#
# This image carries NO application code. Build your app with `node-builder`
# (or any Node build stage) using Next.js `output: 'standalone'`, then `COPY`
# the artifacts into a stage based on this image. Nothing else is needed to
# serve traffic: the standalone server handles static assets itself, so no
# nginx sidecar is required.
#
# One Dockerfile, one image per Node major. `NODE_VERSION` selects the base;
# `variants.json` lists the majors CI builds and which one owns the unsuffixed
# tags. The default here is that same major, so a plain `docker build` with no
# `--build-arg` reproduces the `:latest` image.

ARG NODE_VERSION=22

FROM node:${NODE_VERSION}-alpine

# Redeclared: an ARG stated before the first FROM is in scope only for FROM
# lines. This second declaration inherits the value already passed and makes it
# usable in the build below.
ARG NODE_VERSION

# dumb-init: a real PID 1 that reaps zombies and forwards SIGTERM to the app,
#   so `docker stop` / Kubernetes termination shuts down gracefully instead of
#   being SIGKILLed after the grace period.
# libc6-compat: musl shim for the prebuilt glibc-linked native binaries Next
#   pulls in (@next/swc, and sharp when next/image optimization is used).
RUN apk add --no-cache dumb-init libc6-compat

# Records which base this image was built from, so the Node major is readable
# from `docker inspect` without running the image.
LABEL org.opencontainers.image.base.name="docker.io/library/node:${NODE_VERSION}-alpine"

# Runtime knobs. Override at runtime (docker `-e` / Kubernetes env).
# HOSTNAME=0.0.0.0 is required: the Next standalone server binds localhost
# only by default, which is unreachable from outside the container.
# HEALTHCHECK_PATH is the route the HEALTHCHECK probes — point it at a
# dedicated health route if the app's `/` redirects or is expensive.
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    NEXT_TELEMETRY_DISABLED=1 \
    HEALTHCHECK_PATH=/

COPY docker/healthcheck.sh /usr/local/bin/node-healthcheck
RUN chmod +x /usr/local/bin/node-healthcheck

WORKDIR /app

# .next/cache must be writable by the runtime user: ISR revalidation and
# next/image optimization write there. Created here so the image is sane even
# before an app COPYs its own tree on top; `chown` keeps it owned by the
# unprivileged runtime user.
RUN mkdir -p /app/.next/cache \
    && chown -R node:node /app

# Run as the unprivileged user shipped with the base image.
USER node

# Static metadata mirroring the PORT default. Overriding PORT at runtime does
# not change this line — publish the port you actually configured.
EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD ["node-healthcheck"]

ENTRYPOINT ["dumb-init", "--"]

CMD ["node", "server.js"]
