#!/bin/sh
# Assert the app answers over HTTP on ${HEALTHCHECK_PATH} — not merely that a
# response came back. busybox wget's -S prints the status line (even with -q),
# which we match explicitly, so an unreachable server or a 4xx/5xx both fail
# the check. ${PORT} is read from the environment, so the probe follows the
# configured listen port even when it is overridden with -e.
#
# 2xx and 3xx both pass: a Next app's `/` legitimately 307-redirects under i18n
# or auth middleware, so a strict 200 assertion would false-fail a healthy
# container. Point HEALTHCHECK_PATH at a dedicated route (e.g. /api/health) for
# a strict probe of application readiness.
set -eu

wget -S -q -T 2 -O /dev/null "http://127.0.0.1:${PORT}${HEALTHCHECK_PATH}" 2>&1 \
    | grep -qE 'HTTP/[0-9.]+ [23][0-9][0-9]'
