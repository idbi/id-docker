#!/usr/bin/env bash
set -euo pipefail

# Smoke-tests one locally built image. Usage: smoke-test.sh <component> <image>
#
# The image only needs to exist in the local Docker daemon: CI builds it with
# `load: true`, runs this script and throws it away with the runner, so nothing
# is ever pushed to a registry from a pull request.

component="${1:?usage: smoke-test.sh <component> <image>}"
image="${2:?usage: smoke-test.sh <component> <image>}"

run() { docker run --rm --entrypoint "$1" "$image" "${@:2}"; }

wait_healthy() {
  local name="$1" status=""
  for _ in $(seq 1 30); do
    status=$(docker inspect --format '{{.State.Health.Status}}' "$name" 2>/dev/null || true)
    [ "$status" = "healthy" ] && return 0
    sleep 2
  done
  echo "Container ${name} never became healthy (last status: ${status:-unknown})" >&2
  docker logs "$name" >&2 || true
  return 1
}

case "$component" in
  certbot-renewal)
    run python -c 'import certbot, certbot_dns_route53, boto3'
    ;;
  php-builder)
    run php -v
    run composer --version
    run php -r 'foreach (["pdo_mysql","gd","intl","zip","sodium"] as $e) { if (!extension_loaded($e)) { fwrite(STDERR, "missing $e\n"); exit(1); } }'
    ;;
  php-fpm)
    run php -v
    run php -r 'foreach (["Zend OPcache","pdo_pgsql","redis","gd","intl"] as $e) { if (!extension_loaded($e)) { fwrite(STDERR, "missing $e\n"); exit(1); } }'
    run php-fpm -t
    name="smoke-${component}-$$"
    trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
    docker run -d --name "$name" "$image" >/dev/null
    wait_healthy "$name"
    ;;
  php-nginx)
    name="smoke-${component}-$$"
    trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
    # The server block names a php-fpm host; any resolvable address will do.
    # Healthy means the HEALTHCHECK got an HTTP 200 from /readyz.
    docker run -d --name "$name" --add-host weapp:127.0.0.1 "$image" >/dev/null
    wait_healthy "$name"
    ;;
  node-builder)
    run node -v
    run java -version
    run git --version
    ;;
  node-runtime)
    run node -v
    run sh -c 'test "$(id -u)" != "0" && command -v dumb-init && command -v node-healthcheck'
    ;;
  *)
    echo "No smoke test defined for ${component}" >&2
    exit 1
    ;;
esac

echo "Smoke test passed for ${component} (${image})"
