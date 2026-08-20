"""
Shared boto3 client construction for all scanners.

One botocore config owns connection pooling, timeouts, and retries for
every scanning client:

- max_pool_connections=50 — the scanner fans out regions x services x
  worker threads over shared clients; botocore's default pool of 10
  serializes that fan-out.
- retries mode "adaptive" — botocore is the single owner of
  transient-error retries (client-side rate limiting, Retry-After
  support, full transient error code coverage). No hand-rolled retry
  wrappers on top: stacking them multiplies retry attempts.
"""

from typing import Any

import botocore.config

SCAN_CLIENT_CONFIG = botocore.config.Config(
    max_pool_connections=50,
    retries={"max_attempts": 5, "mode": "adaptive"},
    read_timeout=60,
    connect_timeout=10,
)


def get_scan_client(session: Any, service_name: str, region: str) -> Any:
    """Build a boto3 client for scanning with the shared config."""
    return session.client(service_name, region_name=region, config=SCAN_CLIENT_CONFIG)
