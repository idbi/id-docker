# Changelog

## [1.1.0](https://github.com/idbi/id-docker/compare/php-nginx@v1.0.2...php-nginx@v1.1.0) (2026-08-20)


### Features

* add multi-architecture builds and manifests for Docker images ([0af2021](https://github.com/idbi/id-docker/commit/0af202107e03da3b3c91717b1692d1aa75289ae6))

## [1.0.2](https://github.com/idbi/id-docker/compare/php-nginx@v1.0.1...php-nginx@v1.0.2) (2026-08-12)


### Bug Fixes

* simplify nginx log format by removing redundant `$args` ([e25dc25](https://github.com/idbi/id-docker/commit/e25dc25be9f66922aab03371e835763bc0d64cc4))

## [1.0.1](https://github.com/idbi/id-docker/compare/php-nginx@v1.0.0...php-nginx@v1.0.1) (2026-07-10)


### Bug Fixes

* correct nginx log format spacing ([76fa658](https://github.com/idbi/id-docker/commit/76fa658a3223645205479a8e9942cc63317eac55))

## [1.0.0](https://github.com/idbi/id-docker/compare/php-nginx@v0.3.0...php-nginx@v1.0.0) (2026-07-10)


### ⚠ BREAKING CHANGES

* update NGINX_PHP_FPM_HOST in php-nginx Dockerfile

### Features

* update NGINX_PHP_FPM_HOST in php-nginx Dockerfile ([d7db83a](https://github.com/idbi/id-docker/commit/d7db83ad2f6e8df1866f4f93b870ca721c0cfa92))

## [0.3.0](https://github.com/idbi/id-docker/compare/php-nginx@v0.2.4...php-nginx@v0.3.0) (2026-07-10)


### Features

* configure real IP handling in nginx ([c50cafa](https://github.com/idbi/id-docker/commit/c50cafa3aadf71a3dde8c4ec253b965b57acb8a0))


### Bug Fixes

* disable FPM per-request access log to reduce redundancy ([db03ba7](https://github.com/idbi/id-docker/commit/db03ba7ba75893d38257b65f63ec74a33f841e32))

## [0.2.4](https://github.com/idbi/id-docker/compare/php-nginx@v0.2.3...php-nginx@v0.2.4) (2026-07-04)


### Bug Fixes

* update nginx log_format for improved clarity ([23e800a](https://github.com/idbi/id-docker/commit/23e800a9049f1bad0553996f43ee70248a130c50))

## [0.2.3](https://github.com/idbi/id-docker/compare/php-nginx@v0.2.2...php-nginx@v0.2.3) (2026-07-03)


### Bug Fixes

* remove /readyz readiness endpoint from nginx config ([14d2479](https://github.com/idbi/id-docker/commit/14d2479ea1ce8554e6b65589ebbdd0ce6442a8fa))

## [0.2.2](https://github.com/idbi/id-docker/compare/php-nginx@v0.2.1...php-nginx@v0.2.2) (2026-07-03)


### Bug Fixes

* enhance /readyz healthcheck to verify HTTP 200 status ([7f550c0](https://github.com/idbi/id-docker/commit/7f550c0e2db0b930f21472cc7795063abe0a7b52))

## [0.2.1](https://github.com/idbi/docker/compare/php-nginx@v0.2.0...php-nginx@v0.2.1) (2026-07-03)


### Bug Fixes

* update healthcheck endpoint to /readyz in php-nginx Dockerfile ([c9f034c](https://github.com/idbi/docker/commit/c9f034c4d4f5c425c0205cf78893395802ba61d6))

## [0.2.0](https://github.com/idbi/docker/compare/php-nginx@v0.1.0...php-nginx@v0.2.0) (2026-07-03)


### Features

* add php-nginx frontend for Laravel ([22a8f6d](https://github.com/idbi/docker/commit/22a8f6da6d6a9bbb18e62b0b81e4f524dc7e859a))

## Changelog
