"""--service tab-completion suggests registry service names."""

from cli import complete_service_name
from services.registry import SUPPORTED_SERVICES


def test_empty_prefix_suggests_every_registered_service() -> None:
    assert complete_service_name("") == SUPPORTED_SERVICES


def test_prefix_narrows_suggestions() -> None:
    assert complete_service_name("e") == ["ec2", "ecs", "efs", "elb"]
    assert complete_service_name("rd") == ["rds"]


def test_unknown_prefix_suggests_nothing() -> None:
    assert complete_service_name("cloudfront") == []
