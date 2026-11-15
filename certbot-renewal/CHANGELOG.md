# Changelog

## [2.1.0](https://github.com/idbi/id-docker/compare/certbot-renewal@v2.0.0...certbot-renewal@v2.1.0) (2026-11-15)


### Features

* **certbot-renewal:** add Cloudflare DNS provider ([1310327](https://github.com/idbi/id-docker/commit/1310327d198fa302d057104ed0ed8554cd6478d8))
* **certbot-renewal:** update to Python 3.12.16 and patch dependencies ([726497a](https://github.com/idbi/id-docker/commit/726497a2f0804295dba42d3e1be0cceca0b2a8a3))

## [2.0.0](https://github.com/idbi/id-docker/compare/certbot-renewal@v1.1.0...certbot-renewal@v2.0.0) (2026-08-12)


### ⚠ BREAKING CHANGES

* simplify Vault configuration by replacing `VAULT_CERT_PATH` with `VAULT_MOUNT_POINT` and `VAULT_KEY`

### Code Refactoring

* simplify Vault configuration by replacing `VAULT_CERT_PATH` with `VAULT_MOUNT_POINT` and `VAULT_KEY` ([b9e8e66](https://github.com/idbi/id-docker/commit/b9e8e66495ced047117eae1cb6bdc521f20e65f3))

## [1.1.0](https://github.com/idbi/id-docker/compare/certbot-renewal@v1.0.0...certbot-renewal@v1.1.0) (2026-08-12)


### Features

* enhance logging with configurable log levels and improved error handling ([fa4638b](https://github.com/idbi/id-docker/commit/fa4638b3e7f3261d4c173e44584e69202660c0aa))

## [1.0.0](https://github.com/idbi/id-docker/compare/certbot-renewal@v0.3.1...certbot-renewal@v1.0.0) (2026-08-12)


### ⚠ BREAKING CHANGES

* remove certbot renewal scripts and migrate to Python-based automation

### Features

* update certbot-renewal setup with Vault integration and image adjustments ([16e89fe](https://github.com/idbi/id-docker/commit/16e89feda52144a6d519a9f4bffabc25faeb6a51))


### Bug Fixes

* update perms ([606b38f](https://github.com/idbi/id-docker/commit/606b38f01ca434b7cc89c06ee18938ac66b8f6f5))


### Code Refactoring

* remove certbot renewal scripts and migrate to Python-based automation ([686ac36](https://github.com/idbi/id-docker/commit/686ac36c121829b153b5750f66666589486521e8))
