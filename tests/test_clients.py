"""
Client configuration seam: aws_scanner_lib.clients

Every scanning client must be built with the shared botocore config:
a connection pool sized for the region x service x worker fan-out, and
botocore's adaptive retry mode as the single owner of transient-error
retries (replacing the hand-rolled retry_with_backoff wrapper).
"""

from typing import Any

import boto3

from aws_scanner_lib.clients import SCAN_CLIENT_CONFIG, get_scan_client

REGION = "eu-central-1"


def test_scan_client_config_values() -> None:
    assert SCAN_CLIENT_CONFIG.max_pool_connections == 50
    assert SCAN_CLIENT_CONFIG.retries == {"max_attempts": 5, "mode": "adaptive"}
    assert SCAN_CLIENT_CONFIG.read_timeout == 60
    assert SCAN_CLIENT_CONFIG.connect_timeout == 10
    # CloudTrail-identifiable user agent; already carries the upcoming
    # aws-resource-inventory name.
    assert SCAN_CLIENT_CONFIG.user_agent_extra == "aws-resource-inventory"


def test_get_scan_client_applies_the_shared_config() -> None:
    session = boto3.Session(region_name=REGION)

    client = get_scan_client(session, "ec2", REGION)

    assert client.meta.region_name == REGION
    assert client.meta.config.max_pool_connections == 50
    # botocore normalizes max_attempts=5 to total_max_attempts=6
    # (1 initial call + 5 retries).
    assert client.meta.config.retries == {
        "mode": "adaptive",
        "total_max_attempts": 6,
    }


def test_get_scan_client_passes_service_and_region_through() -> None:
    captured: dict = {}

    class FakeSession:
        def client(self, service_name: str, **kwargs: Any) -> str:
            captured["service_name"] = service_name
            captured.update(kwargs)
            return "the-client"

    assert get_scan_client(FakeSession(), "elbv2", REGION) == "the-client"
    assert captured["service_name"] == "elbv2"
    assert captured["region_name"] == REGION
    assert captured["config"] is SCAN_CLIENT_CONFIG
