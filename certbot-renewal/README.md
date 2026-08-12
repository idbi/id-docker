# Certbot Renewal Automation

This image checks a certificate stored in HashiCorp Vault, obtains an apex and
wildcard certificate through Certbot's Route53 DNS-01 plugin when renewal is
needed, and writes the result to Vault KV v2. The renewal application was
migrated from Bash and the Vault CLI to typed Python code using `hvac`.

## Authentication precedence

The application authenticates with Vault before reading the existing
certificate or starting Certbot:

1. Kubernetes is detected when `KUBERNETES_SERVICE_HOST` is set or the file at
   `VAULT_JWT_PATH` exists.
2. When Kubernetes is detected, the projected ServiceAccount JWT is exchanged
   at the configured Vault Kubernetes auth mount. A successful login always
   wins, even when `VAULT_TOKEN` is also present.
3. If the Kubernetes login fails, a non-empty `VAULT_TOKEN` is validated and
   used as an emergency/backward-compatible fallback.
4. Outside Kubernetes, a non-empty `VAULT_TOKEN` is validated directly.
5. If no method authenticates successfully, the process exits before Certbot.

Fallback is limited to authentication. A Certbot failure or a Vault certificate
read/write failure does not cause a second renewal attempt with the static
token. Kubernetes-issued tokens are revoked on exit when practical. A supplied
`VAULT_TOKEN` is never renewed or revoked automatically and is removed from the
environment passed to Certbot.

The default projected JWT location is `/var/run/secrets/vault/token`. Mount a
ServiceAccount token there or set `VAULT_JWT_PATH` to the projected file.

## Configuration

Required variables:

- `VAULT_ADDR`: Vault server URL. TLS verification is enabled by default.
- `VAULT_CERT_PATH`: KV v2 mount followed by its secret path.
- `DOMAIN`: certificate name and apex DNS name.
- `EMAIL`: Let's Encrypt account email.

Vault authentication variables:

- `VAULT_ROLE`: Kubernetes auth role; defaults to `certbot-renewal`.
- `VAULT_AUTH_PATH`: Kubernetes auth mount; defaults to `kubernetes`.
- `VAULT_JWT_PATH`: projected token file; defaults to
  `/var/run/secrets/vault/token`.
- `VAULT_TOKEN`: optional controlled fallback. The token needs
  `auth/token/lookup-self` read permission in addition to certificate access.
- `VAULT_CACERT`: optional CA bundle for a private Vault CA.

Renewal variables:

- `DAYS_THRESHOLD`: renew when the stored certificate expires within this many
  days; defaults to `30`.

Logging variables:

- `LOG_LEVEL`: `INFO` (the default), `DEBUG`, `TRACE`, `WARNING`, `ERROR`, or
  `CRITICAL`. `DEBUG` reports authentication discovery, Vault endpoints, roles,
  paths, TLS settings, and sanitized remote error details. `TRACE` additionally
  prints partially redacted markers for the Kubernetes JWT and Vault tokens so a
  credential can be correlated across events without disclosing its full value.

For authentication troubleshooting, start with:

```sh
LOG_LEVEL=DEBUG
```

Use `TRACE` only when token correlation is needed. For credentials longer than
eight characters, a marker shows the first and last four characters with the
middle replaced by `...`. Shorter values show only their first and last
character; values of two or fewer characters remain fully masked. The marker
also contains the credential length and the first 12 hexadecimal characters of
its SHA-256 digest. Request and response bodies are never logged.

Route53 authentication continues to use the standard AWS credential chain.
Common variables include `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, optional
`AWS_SESSION_TOKEN`, and `AWS_DEFAULT_REGION`. The Vault token is removed from
the Certbot child environment; AWS variables are preserved.

### Vault path and policy

`VAULT_CERT_PATH=idbi/certificates/nginx` is parsed as:

- KV v2 mount: `idbi`
- secret path: `certificates/nginx`
- HTTP API path: `idbi/data/certificates/nginx`

The secret contains the existing field names `fullchain` and `privkey`. The
Vault policy needs read access to inspect `fullchain` and create/update access
to store both fields. Static fallback validation may require:

```hcl
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
```

## Certbot behavior

Certbot requests both `DOMAIN` and `*.DOMAIN` with `--dns-route53`, uses
`DOMAIN` as `--cert-name`, and keeps the existing non-interactive, terms,
email, config, work, and ephemeral log options. Files are read from:

```text
/etc/letsencrypt/live/<DOMAIN>/fullchain.pem
/etc/letsencrypt/live/<DOMAIN>/privkey.pem
```

Both files must exist and be non-empty before the Vault write occurs. The
application never logs raw JWTs, raw Vault tokens, AWS credentials, certificate
values, private keys, complete subprocess environments, request bodies, or raw
Vault responses. `TRACE` can log partially redacted credential markers as
described above; those markers intentionally reveal a few credential
characters.

## Build and run

Build from the repository root:

```sh
docker build -t local/certbot-renewal:test ./certbot-renewal
```

Kubernetes should project a ServiceAccount token and configure the Vault role.
For a local or emergency static-token run:

```sh
docker run --rm \
  -e VAULT_ADDR="https://vault.example.com" \
  -e VAULT_CERT_PATH="idbi/certificates/nginx" \
  -e VAULT_TOKEN="..." \
  -e DOMAIN="example.com" \
  -e EMAIL="admin@example.com" \
  -e AWS_ACCESS_KEY_ID="..." \
  -e AWS_SECRET_ACCESS_KEY="..." \
  local/certbot-renewal:test
```
