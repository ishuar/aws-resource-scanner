# Changelog

## [0.1.1](https://github.com/ishuar/aws-resource-inventory/compare/v0.1.0...v0.1.1) (2026-08-22)


### 🐞 Bug Fixes

* e2e-diff refuses refs it cannot honestly compare ([#48](https://github.com/ishuar/aws-resource-inventory/issues/48)) ([215d844](https://github.com/ishuar/aws-resource-inventory/commit/215d8444da39a9a9abfd69df978dae588de63912))
* installed CLI starts — ship cli.py and aws_scanner.py in the wheel ([#45](https://github.com/ishuar/aws-resource-inventory/issues/45)) ([c926547](https://github.com/ishuar/aws-resource-inventory/commit/c9265477c50153761a729c2076fea40d2152a1d0))
* release pipeline publishes to PyPI, and packaging is checked before release ([#42](https://github.com/ishuar/aws-resource-inventory/issues/42)) ([b4d7935](https://github.com/ishuar/aws-resource-inventory/commit/b4d7935dc48741a4e41d7aea6e46570b9dc5c179))


### 📦 Other Changes

* everything ships inside one aws_resource_inventory package ([#47](https://github.com/ishuar/aws-resource-inventory/issues/47)) ([2f284e9](https://github.com/ishuar/aws-resource-inventory/commit/2f284e98e15187253b665cad4b31162724dffc9f))
* install from PyPI with uv or pipx ([#46](https://github.com/ishuar/aws-resource-inventory/issues/46)) ([b80f403](https://github.com/ishuar/aws-resource-inventory/commit/b80f4034b48744da3b1e948b97cf0ef0c70a6eae))

## 0.1.0 (2026-08-22)

Initial release of **aws-resource-inventory** — a read-only CLI
(`aws-inventory`) that inventories AWS resources across regions and
services.

### ✨ Highlights

* Scans eight AWS services — EC2, S3, ECS, EFS, VPC, RDS, ELB, and Auto Scaling — across multiple regions concurrently, with or without tag filters.
* Discovers resources from 100+ AWS services via the Resource Groups Tagging API (`--all-services` with a tag filter).
* Table, JSON, and Markdown output — rendered in the terminal and written to a file for further processing.
* Result caching with a 10-minute TTL, configurable parallelism per region (`--max-workers`) and per service (`--service-workers`), dry-run preview, continuous refresh mode, and graceful Ctrl+C handling.
* Debug traces (`--debug`), full AWS API tracing (`--verbose`), custom log files (`--log-file`), and shell tab-completion for commands, options, and service names.

Install: `pip install aws-resource-inventory`
