"""
Record seam: aws_resource_inventory.lib.records.Resource — the one definition of
the scan-record shape every producer constructs and every output
consumes. A malformed record fails at construction, not at report time.
"""

import dataclasses
from typing import Any

import pytest

from aws_resource_inventory.lib.records import Resource

REGION = "eu-central-1"


def make(**overrides: Any) -> Resource:
    fields: dict[str, Any] = {
        "region": REGION,
        "resource_type": "s3:bucket",
        "resource_id": "my-bucket",
        "resource_arn": "arn:aws:s3:::my-bucket",
    }
    fields.update(overrides)
    return Resource(**fields)


def test_missing_required_field_fails_at_construction() -> None:
    with pytest.raises(TypeError):
        Resource(region=REGION, resource_type="s3:bucket", resource_id="b")  # type: ignore[call-arg]


def test_records_are_immutable() -> None:
    resource = make()
    with pytest.raises(dataclasses.FrozenInstanceError):
        resource.resource_id = "other"  # type: ignore[misc]


def test_to_record_without_name_matches_the_legacy_dict_exactly() -> None:
    # Key ORDER matters: JSON output must stay byte-identical with the
    # dicts producers used to build by hand.
    assert list(make().to_record().items()) == [
        ("region", REGION),
        ("resource_type", "s3:bucket"),
        ("resource_id", "my-bucket"),
        ("resource_arn", "arn:aws:s3:::my-bucket"),
    ]


def test_to_record_with_name_places_it_second_like_the_legacy_dicts() -> None:
    record = make(resource_name="friendly").to_record()
    assert list(record) == [
        "region",
        "resource_name",
        "resource_type",
        "resource_id",
        "resource_arn",
    ]
    assert record["resource_name"] == "friendly"


def test_name_defaults_to_absent() -> None:
    assert "resource_name" not in make().to_record()
    assert make().resource_name is None


def test_service_is_derived_from_the_resource_type_prefix() -> None:
    assert make(resource_type="ec2:instance").service == "ec2"
    # Bare types without a colon (the legacy "vpc" form) are their own service.
    assert make(resource_type="vpc").service == "vpc"
