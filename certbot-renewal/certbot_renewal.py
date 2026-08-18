"""Certbot renewal and Vault KV-v2 storage automation."""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import hvac
import requests
from cryptography import x509

logger = logging.getLogger(__name__)

TRACE = 5
LOG_LEVELS = {
    "TRACE": TRACE,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

LETSENCRYPT_CONFIG_DIR = Path("/etc/letsencrypt")
LETSENCRYPT_WORK_DIR = Path("/var/lib/letsencrypt")


class ConfigurationError(ValueError):
    """Raised when application configuration is missing or invalid."""


class VaultAuthenticationError(RuntimeError):
    """A sanitized Vault authentication failure."""


class CertificateFileError(RuntimeError):
    """Raised when Certbot output files cannot be safely loaded."""


class AuthenticationSource(Enum):
    KUBERNETES = "kubernetes"
    STATIC_TOKEN = "static-token"


@dataclass
class AuthenticatedVaultClient:
    client: hvac.Client = field(repr=False)
    source: AuthenticationSource
    revoke_on_exit: bool


@dataclass(frozen=True)
class Config:
    """Validated configuration with credentials excluded from representations."""

    vault_addr: str
    vault_mount_point: str
    vault_key: str
    domain: str
    email: str
    vault_role: str = "certbot-renewal"
    vault_auth_path: str = "kubernetes"
    vault_jwt_path: Path = Path("/var/run/secrets/vault/token")
    vault_token: str | None = field(default=None, repr=False)
    vault_cacert: Path | None = None
    days_threshold: int = 30

    @classmethod
    def from_env(cls, environment: Mapping[str, str] | None = None) -> Config:
        env = os.environ if environment is None else environment
        vault_mount_point = _required(env, "VAULT_MOUNT_POINT").strip("/")
        vault_key = _required(env, "VAULT_KEY").strip("/")
        if not vault_mount_point:
            raise ConfigurationError("VAULT_MOUNT_POINT must not be empty")
        if not vault_key:
            raise ConfigurationError("VAULT_KEY must not be empty")

        raw_threshold = env.get("DAYS_THRESHOLD", "30").strip()
        try:
            days_threshold = int(raw_threshold)
        except ValueError as exc:
            raise ConfigurationError(
                "DAYS_THRESHOLD must be a non-negative integer"
            ) from exc
        if days_threshold < 0:
            raise ConfigurationError("DAYS_THRESHOLD must be a non-negative integer")

        vault_role = env.get("VAULT_ROLE", "certbot-renewal").strip()
        vault_auth_path = env.get("VAULT_AUTH_PATH", "kubernetes").strip("/").strip()
        jwt_path = env.get("VAULT_JWT_PATH", "/var/run/secrets/vault/token").strip()
        if not vault_role:
            raise ConfigurationError("VAULT_ROLE must not be empty")
        if not vault_auth_path:
            raise ConfigurationError("VAULT_AUTH_PATH must not be empty")
        if not jwt_path:
            raise ConfigurationError("VAULT_JWT_PATH must not be empty")

        token = env.get("VAULT_TOKEN", "").strip() or None
        cacert = env.get("VAULT_CACERT", "").strip()
        return cls(
            vault_addr=_required(env, "VAULT_ADDR"),
            vault_mount_point=vault_mount_point,
            vault_key=vault_key,
            domain=_required(env, "DOMAIN"),
            email=_required(env, "EMAIL"),
            vault_role=vault_role,
            vault_auth_path=vault_auth_path,
            vault_jwt_path=Path(jwt_path),
            vault_token=token,
            vault_cacert=Path(cacert) if cacert else None,
            days_threshold=days_threshold,
        )


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"Required environment variable {name} is not set")
    return value


def _configure_logging(environment: Mapping[str, str]) -> None:
    raw_level = environment.get("LOG_LEVEL", "INFO").strip().upper()
    level = LOG_LEVELS.get(raw_level)
    if level is None:
        supported = ", ".join(LOG_LEVELS)
        raise ConfigurationError(f"LOG_LEVEL must be one of: {supported}")

    logging.addLevelName(TRACE, "TRACE")
    logging.basicConfig(
        # Keep dependency loggers at INFO or above; some HTTP/AWS libraries may
        # expose more context than this application can safely sanitize.
        level=max(level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger.setLevel(level)
    logger.debug("Logging initialized at %s level", raw_level)


def _trace(message: str, *args: Any) -> None:
    logger.log(TRACE, message, *args)


def _secret_marker(name: str, value: str) -> str:
    """Return a stable token marker with only a small prefix and suffix visible."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    if len(value) > 8:
        marked = f"{value[:4]}...{value[-4:]}"
    elif len(value) > 2:
        marked = f"{value[:1]}...{value[-1:]}"
    else:
        marked = "***" if value else "<empty>"
    return f"<{name}:{marked} length={len(value)} sha256={digest}>"


def _redact(value: object, secrets: tuple[str, ...] = ()) -> str:
    sanitized = " ".join(str(value).split())
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "<redacted>")
    return sanitized


def _safe_url(value: str) -> str:
    """Remove credentials, query parameters, and fragments from a logged URL."""
    parsed = urlsplit(value)
    hostname = parsed.hostname or ""
    if ":" in hostname:
        hostname = f"[{hostname}]"
    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _log_remote_error(
    operation: str,
    exc: Exception,
    *,
    secrets: tuple[str, ...] = (),
) -> None:
    detail = _redact(exc, secrets) or "no error details returned"
    logger.debug("%s failed: %s: %s", operation, type(exc).__name__, detail)

    request = getattr(exc, "request", None)
    response = getattr(exc, "response", None)
    method = getattr(exc, "method", None) or getattr(request, "method", None)
    url = getattr(exc, "url", None) or getattr(request, "url", None)
    status_code = getattr(exc, "status_code", None) or getattr(
        response, "status_code", None
    )
    _trace(
        "%s failure metadata: method=%s url=%s status=%s",
        operation,
        method or "unknown",
        _safe_url(_redact(url, secrets)) if url else "unknown",
        status_code if status_code is not None else "unknown",
    )


def _vault_client(config: Config, token: str | None = None) -> hvac.Client:
    verify: bool | str = str(config.vault_cacert) if config.vault_cacert else True
    logger.debug(
        "Creating Vault client: address=%s tls_verify=%s token_supplied=%s",
        _safe_url(config.vault_addr),
        verify,
        token is not None,
    )
    if token is not None:
        _trace("Static Vault token: %s", _secret_marker("vault-token", token))
    return hvac.Client(url=config.vault_addr, token=token, verify=verify)


def _client_token(response: Any) -> str:
    if not isinstance(response, Mapping):
        raise VaultAuthenticationError(
            "Vault Kubernetes authentication returned a malformed response"
        )
    auth = response.get("auth")
    if not isinstance(auth, Mapping):
        raise VaultAuthenticationError(
            "Vault Kubernetes authentication returned a malformed response"
        )
    token = auth.get("client_token")
    if not isinstance(token, str) or not token.strip():
        raise VaultAuthenticationError(
            "Vault Kubernetes authentication returned no client token"
        )
    return token.strip()


def authenticate_with_kubernetes(config: Config) -> AuthenticatedVaultClient:
    logger.debug(
        "Reading Kubernetes ServiceAccount JWT: path=%s role=%s auth_mount=%s",
        config.vault_jwt_path,
        config.vault_role,
        config.vault_auth_path,
    )
    try:
        jwt = config.vault_jwt_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        logger.debug(
            "Unable to read Kubernetes ServiceAccount JWT at %s: %s: %s",
            config.vault_jwt_path,
            type(exc).__name__,
            _redact(exc),
        )
        raise VaultAuthenticationError(
            "Unable to read the Kubernetes ServiceAccount JWT"
        ) from exc
    if not jwt:
        raise VaultAuthenticationError("The Kubernetes ServiceAccount JWT is empty")

    _trace("Kubernetes JWT: %s", _secret_marker("kubernetes-jwt", jwt))
    client = _vault_client(config)
    logger.debug(
        "Vault remote call: POST %s/v1/auth/%s/login role=%s",
        _safe_url(config.vault_addr).rstrip("/"),
        config.vault_auth_path,
        config.vault_role,
    )
    try:
        response = client.auth.kubernetes.login(
            role=config.vault_role,
            jwt=jwt,
            mount_point=config.vault_auth_path,
        )
        token = _client_token(response)
        _trace(
            "Vault Kubernetes login returned a client token: %s",
            _secret_marker("vault-token", token),
        )
        del response
    except (hvac.exceptions.VaultError, requests.exceptions.RequestException) as exc:
        _log_remote_error("Vault Kubernetes login", exc, secrets=(jwt,))
        raise VaultAuthenticationError(
            "Vault Kubernetes authentication request failed"
        ) from exc
    finally:
        jwt = ""

    client.token = token
    return AuthenticatedVaultClient(
        client=client,
        source=AuthenticationSource.KUBERNETES,
        revoke_on_exit=True,
    )


def authenticate_with_static_token(config: Config) -> AuthenticatedVaultClient:
    token = (config.vault_token or "").strip()
    if not token:
        raise VaultAuthenticationError("No static Vault token is configured")

    client = _vault_client(config, token=token)
    logger.debug(
        "Vault remote call: GET %s/v1/auth/token/lookup-self",
        _safe_url(config.vault_addr).rstrip("/"),
    )
    try:
        client.auth.token.lookup_self()
    except (hvac.exceptions.VaultError, requests.exceptions.RequestException) as exc:
        _log_remote_error("Vault static-token lookup", exc, secrets=(token,))
        raise VaultAuthenticationError("Vault static-token validation failed") from exc

    return AuthenticatedVaultClient(
        client=client,
        source=AuthenticationSource.STATIC_TOKEN,
        revoke_on_exit=False,
    )


def authenticate(config: Config) -> AuthenticatedVaultClient:
    service_host_present = bool(os.getenv("KUBERNETES_SERVICE_HOST"))
    jwt_path_exists = config.vault_jwt_path.exists()
    kubernetes_detected = service_host_present or jwt_path_exists
    kubernetes_error: VaultAuthenticationError | None = None
    logger.debug(
        "Authentication discovery: kubernetes_service_host=%s jwt_path=%s "
        "jwt_exists=%s static_fallback=%s",
        service_host_present,
        config.vault_jwt_path,
        jwt_path_exists,
        config.vault_token is not None,
    )

    if kubernetes_detected:
        logger.info("Kubernetes detected; attempting Vault Kubernetes authentication")
        try:
            return authenticate_with_kubernetes(config)
        except VaultAuthenticationError as exc:
            kubernetes_error = exc
            logger.warning(
                "Vault Kubernetes authentication failed (%s); checking configured "
                "fallback",
                exc,
            )

    if config.vault_token:
        logger.info("Attempting Vault static-token authentication")
        try:
            return authenticate_with_static_token(config)
        except VaultAuthenticationError as exc:
            logger.error("Vault static-token authentication failed: %s", exc)
            raise

    if kubernetes_error is not None:
        raise VaultAuthenticationError(
            "Vault Kubernetes authentication failed and no static-token fallback "
            "is configured"
        )
    raise VaultAuthenticationError(
        "No supported Vault authentication method is configured"
    )


def read_stored_certificate(client: hvac.Client, config: Config) -> str | None:
    logger.debug(
        "Vault remote call: GET %s/v1/%s/data/%s",
        _safe_url(config.vault_addr).rstrip("/"),
        config.vault_mount_point,
        config.vault_key,
    )
    try:
        response = client.secrets.kv.v2.read_secret_version(
            mount_point=config.vault_mount_point,
            path=config.vault_key,
        )
    except hvac.exceptions.InvalidPath:
        return None

    if not isinstance(response, Mapping):
        return None
    outer_data: Any = response.get("data")
    if not isinstance(outer_data, Mapping):
        return None
    secret: Any = outer_data.get("data")
    if not isinstance(secret, Mapping):
        return None
    certificate = secret.get("fullchain")
    return certificate if isinstance(certificate, str) and certificate else None


def certificate_needs_renewal(certificate: str | None, days_threshold: int) -> bool:
    if certificate is None:
        logger.warning("No certificate is stored in Vault; renewal is required")
        return True
    try:
        parsed = x509.load_pem_x509_certificate(certificate.encode("utf-8"))
    except ValueError:
        logger.warning(
            "The certificate stored in Vault is invalid; renewal is required"
        )
        return True

    renewal_at = datetime.now(UTC) + timedelta(days=days_threshold)
    if parsed.not_valid_after_utc > renewal_at:
        logger.info(
            "Certificate is valid beyond the %d-day threshold; no renewal is required",
            days_threshold,
        )
        return False
    logger.info(
        "Certificate expires within %d days; renewal is required", days_threshold
    )
    return True


def run_certbot(config: Config) -> None:
    child_env = os.environ.copy()
    child_env.pop("VAULT_TOKEN", None)

    with tempfile.TemporaryDirectory(prefix="certbot-logs.") as directory:
        logs_dir = Path(directory)
        (logs_dir / "letsencrypt.log").symlink_to("/dev/null")
        command = [
            "certbot",
            "certonly",
            "--dns-route53",
            "--domains",
            config.domain,
            "--domains",
            f"*.{config.domain}",
            "--cert-name",
            config.domain,
            "--non-interactive",
            "--agree-tos",
            "--email",
            config.email,
            "--config-dir",
            str(LETSENCRYPT_CONFIG_DIR),
            "--work-dir",
            str(LETSENCRYPT_WORK_DIR),
            "--logs-dir",
            str(logs_dir),
            "--max-log-backups",
            "0",
        ]
        subprocess.run(
            command,
            check=True,
            text=True,
            shell=False,
            env=child_env,
        )


def _read_nonempty(path: Path, description: str) -> str:
    try:
        value = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CertificateFileError(
            f"The {description} file is missing or unreadable"
        ) from exc
    if not value:
        raise CertificateFileError(f"The {description} file is empty")
    return value


def read_certificate_files(config: Config) -> tuple[str, str]:
    certificate_dir = LETSENCRYPT_CONFIG_DIR / "live" / config.domain
    return (
        _read_nonempty(certificate_dir / "fullchain.pem", "certificate"),
        _read_nonempty(certificate_dir / "privkey.pem", "private key"),
    )


def store_certificate(
    client: hvac.Client,
    config: Config,
    fullchain: str,
    privkey: str,
) -> None:
    logger.debug(
        "Vault remote call: POST %s/v1/%s/data/%s",
        _safe_url(config.vault_addr).rstrip("/"),
        config.vault_mount_point,
        config.vault_key,
    )
    client.secrets.kv.v2.create_or_update_secret(
        mount_point=config.vault_mount_point,
        path=config.vault_key,
        secret={"fullchain": fullchain, "privkey": privkey},
    )


def renew_and_store(client: hvac.Client, config: Config) -> None:
    certificate = read_stored_certificate(client, config)
    if not certificate_needs_renewal(certificate, config.days_threshold):
        return

    logger.info(
        "Requesting an apex and wildcard certificate with Route53 DNS validation"
    )
    run_certbot(config)
    fullchain, privkey = read_certificate_files(config)
    store_certificate(client, config, fullchain, privkey)
    logger.info("Certificate and private key stored in Vault successfully")


def run(config: Config) -> None:
    authenticated: AuthenticatedVaultClient | None = None
    try:
        authenticated = authenticate(config)
        logger.info(
            "Vault authentication succeeded using %s",
            authenticated.source.value,
        )
        renew_and_store(authenticated.client, config)
    finally:
        if authenticated is not None and authenticated.revoke_on_exit:
            logger.debug("Vault remote call: POST auth/token/revoke-self")
            try:
                authenticated.client.auth.token.revoke_self()
            except Exception as exc:
                logger.warning("Unable to revoke the temporary Vault token")
                _log_remote_error("Vault token revocation", exc)


def main() -> int:
    try:
        _configure_logging(os.environ)
        run(Config.from_env())
    except (ConfigurationError, VaultAuthenticationError) as exc:
        logger.error("%s", exc)
        return 1
    except subprocess.CalledProcessError as exc:
        logger.error("Certbot failed with exit code %s", exc.returncode)
        return 1
    except CertificateFileError as exc:
        logger.error("%s", exc)
        return 1
    except (hvac.exceptions.VaultError, requests.exceptions.RequestException) as exc:
        logger.error("Vault certificate operation failed")
        _log_remote_error("Vault certificate operation", exc)
        return 1
    except OSError as exc:
        logger.error("A local certificate operation failed")
        logger.debug(
            "Local certificate operation failed: %s: %s",
            type(exc).__name__,
            _redact(exc),
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
