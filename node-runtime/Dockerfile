# Production-ready Node.js runtime for Next.js applications.
#
# This image carries NO application code. Build your app with `node-builder`
# (or any Node build stage) using Next.js `output: 'standalone'`, then `COPY`
# the artifacts into a stage based on this image. Nothing else is needed to
# serve traffic: the standalone server handles static assets itself, so no
# nginx sidecar is required.

FROM node:22-alpine

# dumb-init: a real PID 1 that reaps zombies and forwards SIGTERM to the app,
#   so `docker stop` / Kubernetes termination shuts down gracefully instead of
#   being SIGKILLed after the grace period.
# libc6-compat: musl shim for the prebuilt glibc-linked native binaries Next
#   pulls in (@next/swc, and sharp when next/image optimization is used).
RUN apk add --no-cache dumb-init libc6-compat

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
