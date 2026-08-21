"""
ARN parsing seam: aws_scanner_lib.resource_groups_utils

These functions decide how every Resource-Groups-discovered resource is
identified in the output. Expected values are worked examples from the AWS
ARN documentation format: arn:partition:service:region:account:resource.
"""

from aws_scanner_lib.resource_groups_utils import (
    _extract_resource_id_from_arn,
    _extract_service_and_type_from_arn,
    should_use_resource_groups_api,
)


class TestExtractServiceAndType:
    def test_slash_separated_resource(self) -> None:
        arn = "arn:aws:ec2:eu-central-1:111122223333:instance/i-0abcd1234"
        assert _extract_service_and_type_from_arn(arn) == ("ec2", "instance")

    def test_colon_separated_resource(self) -> None:
        arn = "arn:aws:sns:eu-central-1:111122223333:my-topic"
        assert _extract_service_and_type_from_arn(arn) == ("sns", "my-topic")

    def test_s3_bucket_arn_has_empty_region_and_account(self) -> None:
        # arn:aws:s3:::bucket-name — the resource part is the bucket name
        arn = "arn:aws:s3:::my-bucket"
        assert _extract_service_and_type_from_arn(arn) == ("s3", "my-bucket")

    def test_malformed_arn_yields_empty_pair(self) -> None:
        assert _extract_service_and_type_from_arn("not-an-arn") == ("", "")
        assert _extract_service_and_type_from_arn("") == ("", "")


class TestExtractResourceId:
    def test_s3_bucket_id_is_the_bucket_name(self) -> None:
        arn = "arn:aws:s3:::my-bucket"
        assert _extract_resource_id_from_arn(arn, "s3:bucket") == "my-bucket"

    def test_load_balancer_keeps_type_name_and_id(self) -> None:
        arn = (
            "arn:aws:elasticloadbalancing:eu-central-1:111122223333:"
            "loadbalancer/app/my-alb/50dc6c495c0c9188"
        )
        assert (
            _extract_resource_id_from_arn(arn, "elasticloadbalancing:loadbalancer")
            == "app/my-alb/50dc6c495c0c9188"
        )

    def test_target_group_keeps_name_and_id(self) -> None:
        arn = (
            "arn:aws:elasticloadbalancing:eu-central-1:111122223333:"
            "targetgroup/my-tg/73e2d6bc24d8a067"
        )
        assert (
            _extract_resource_id_from_arn(arn, "elasticloadbalancing:targetgroup")
            == "my-tg/73e2d6bc24d8a067"
        )

    def test_generic_slash_resource_takes_last_segment(self) -> None:
        arn = "arn:aws:ec2:eu-central-1:111122223333:instance/i-0abcd1234"
        assert _extract_resource_id_from_arn(arn, "ec2:instance") == "i-0abcd1234"

    def test_colon_only_resource_takes_last_segment(self) -> None:
        arn = "arn:aws:sns:eu-central-1:111122223333:my-topic"
        assert _extract_resource_id_from_arn(arn, "sns:my-topic") == "my-topic"

    def test_other_elb_subtypes_fall_through_to_none(self) -> None:
        # Characterization: listener ARNs start with "elasticloadbalancing:"
        # but match neither the loadbalancer nor the targetgroup branch, so
        # the current implementation returns None for them (the generic
        # slash-splitting is never reached). If a refactor improves this,
        # update the expectation deliberately.
        arn = (
            "arn:aws:elasticloadbalancing:eu-central-1:111122223333:"
            "listener/app/my-alb/50dc6c495c0c9188/f2f7dc8efc522ab2"
        )
        assert (
            _extract_resource_id_from_arn(arn, "elasticloadbalancing:listener") is None
        )


class TestShouldUseResourceGroupsApi:
    def test_any_tag_triggers_the_tag_path(self) -> None:
        assert should_use_resource_groups_api("env", "prod") is True
        assert should_use_resource_groups_api("env", None) is True
        assert should_use_resource_groups_api(None, "prod") is True

    def test_no_tags_means_traditional_path(self) -> None:
        assert should_use_resource_groups_api(None, None) is False
