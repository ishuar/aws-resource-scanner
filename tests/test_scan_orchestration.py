"""
Scan orchestration seam: aws_scanner_lib.scan

scan_service and scan_region are the interface the CLI drives. These tests
exercise dispatch, caching, error swallowing, service filtering, shutdown,
and progress reporting through that interface only — no reaching into the
dispatch mechanism — so they must keep passing unchanged through the
planned service-registry and spec-driven-scanner refactors.
"""

import threading
from typing import Any, List, Tuple

from botocore.exceptions import ClientError

from aws_scanner_lib.cache import cache_result
from aws_scanner_lib.scan import scan_region, scan_service

REGION = "eu-central-1"


def client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "DescribeThings")


class TestScanService:
    def test_unknown_service_returns_empty_dict(self, aws_session: Any) -> None:
        assert scan_service(aws_session, REGION, "not-a-service", use_cache=False) == {}

    def test_cache_hit_short_circuits_the_scan(self) -> None:
        # session=None: any attempt to actually scan would crash. Returning
        # the cached payload proves AWS is never touched on a hit.
        cached = {"buckets": [{"Name": "from-cache"}]}
        cache_result(REGION, "s3", cached)

        assert scan_service(None, REGION, "s3", use_cache=True) == cached

    def test_scan_result_is_stored_in_the_cache(self, aws_session: Any) -> None:
        aws_session.client("s3", region_name=REGION).create_bucket(
            Bucket="cached-bucket",
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )

        first = scan_service(aws_session, REGION, "s3", use_cache=True)
        assert [b["Name"] for b in first["buckets"]] == ["cached-bucket"]

        # Second call with a session that cannot scan → must come from cache.
        assert scan_service(None, REGION, "s3", use_cache=True) == first

    def test_no_cache_flag_bypasses_a_poisoned_cache(self, aws_session: Any) -> None:
        cache_result(REGION, "s3", {"buckets": [{"Name": "stale"}]})
        result = scan_service(aws_session, REGION, "s3", use_cache=False)
        assert result == {"buckets": []}

    def test_tag_filters_are_forwarded_to_the_autoscaling_scanner(
        self, aws_session: Any
    ) -> None:
        # autoscaling is the one service whose scanner accepts tag filters
        # (RGTA doesn't cover ASGs); scan_service must pass them through.
        ec2 = aws_session.client("ec2", region_name=REGION)
        autoscaling = aws_session.client("autoscaling", region_name=REGION)
        ec2.create_launch_template(
            LaunchTemplateName="disp-lt",
            LaunchTemplateData={"ImageId": "ami-12345678", "InstanceType": "t3.micro"},
        )
        for name, tags in [
            ("prod-asg", [{"Key": "env", "Value": "prod"}]),
            ("dev-asg", []),
        ]:
            autoscaling.create_auto_scaling_group(
                AutoScalingGroupName=name,
                MinSize=0,
                MaxSize=1,
                AvailabilityZones=[f"{REGION}a"],
                LaunchTemplate={"LaunchTemplateName": "disp-lt"},
                Tags=[
                    {**t, "ResourceId": name, "ResourceType": "auto-scaling-group"}
                    for t in tags
                ],
            )

        result = scan_service(
            aws_session, REGION, "autoscaling", "env", "prod", use_cache=False
        )

        assert [a["AutoScalingGroupName"] for a in result["auto_scaling_groups"]] == [
            "prod-asg"
        ]

    def test_client_error_from_a_scanner_is_swallowed_to_empty(self) -> None:
        class BrokenSession:
            def client(self, *_args: Any, **_kwargs: Any) -> Any:
                raise client_error("AccessDenied")

        assert scan_service(BrokenSession(), REGION, "s3", use_cache=False) == {}


class TestScanRegion:
    def test_scans_requested_services_and_reports_progress(
        self, aws_session: Any
    ) -> None:
        aws_session.client("s3", region_name=REGION).create_bucket(
            Bucket="region-bucket",
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )

        progress_calls: List[Tuple[int, int, str, str]] = []

        def on_progress(completed: int, total: int, service: str, region: str) -> None:
            progress_calls.append((completed, total, service, region))

        region, results, duration = scan_region(
            aws_session,
            REGION,
            services=["s3"],
            use_cache=False,
            progress_callback=on_progress,
        )

        assert region == REGION
        assert [b["Name"] for b in results["s3"]["buckets"]] == ["region-bucket"]
        assert duration >= 0
        assert progress_calls == [(1, 1, "s3", REGION)]

    def test_unsupported_services_are_silently_filtered(self, aws_session: Any) -> None:
        progress_calls: List[Tuple[int, int, str, str]] = []

        _, results, _ = scan_region(
            aws_session,
            REGION,
            services=["s3", "dynamodb", "bogus"],
            use_cache=False,
            progress_callback=lambda *args: progress_calls.append(args),
        )

        assert "dynamodb" not in results
        assert "bogus" not in results
        # Only the supported service was submitted and counted.
        assert all(total == 1 for _, total, _, _ in progress_calls)

    def test_service_with_no_resources_is_omitted_from_results(
        self, aws_session: Any
    ) -> None:
        # Characterization: an empty scan result ({} or all-empty values is
        # still truthy for dicts with keys, but a falsy {} is dropped).
        # s3 with no buckets returns {"buckets": []} (truthy) and is kept.
        _, results, _ = scan_region(
            aws_session, REGION, services=["s3"], use_cache=False
        )
        assert results["s3"] == {"buckets": []}

    def test_pre_set_shutdown_event_stops_before_collecting_results(
        self, aws_session: Any
    ) -> None:
        shutdown = threading.Event()
        shutdown.set()

        _, results, _ = scan_region(
            aws_session,
            REGION,
            services=["s3"],
            use_cache=False,
            shutdown_event=shutdown,
        )

        assert results == {}
