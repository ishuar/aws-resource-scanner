# Changelog

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
