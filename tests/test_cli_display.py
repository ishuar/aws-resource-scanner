"""
Configuration-panel seam: the Workers row describes the parallelism the scan
will actually use, not the --max-workers/--service-workers caps verbatim.

Real expectations pinned here:
- worker counts are bounded by the actual work (regions to scan, services
  requested), with the flag caps as upper limits — mirroring the pools in
  aws_scanner.py (regions) and aws_scanner_lib/scan.py (services);
- tag mode and --all-services fan out per region only (Resource Groups
  API), so the services multiplier must not appear there;
- grammar stays correct for single region/service.
"""

from typing import Any

from rich.console import Console

import cli as cli_module


def render_config_panel(monkeypatch: Any, **overrides: Any) -> str:
    """Render the configuration panel and return its plain text."""
    params: dict[str, Any] = {
        "all_services": False,
        "tag_key": None,
        "tag_value": None,
        "services": ["efs"],
        "region_list": [
            "eu-north-1",
            "eu-west-1",
            "eu-west-2",
            "eu-west-3",
            "eu-central-1",
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
        ],
        "max_workers": 8,
        "service_workers": 4,
        "use_cache": True,
        "refresh": False,
        "refresh_interval": 10,
        "output_format": "table",
        "aws_profile": "test-profile",
        "debug": False,
    }
    params.update(overrides)

    capture_console = Console(width=200, force_terminal=False)
    monkeypatch.setattr(cli_module, "console", capture_console)
    with capture_console.capture() as capture:
        cli_module._display_configuration_panel(**params)
    return capture.get()


class TestWorkersRow:
    def test_single_service_shows_one_service_worker_not_the_cap(
        self, monkeypatch: Any
    ) -> None:
        # 9 regions capped at 8 workers; 1 service needs 1 worker, not 4.
        text = render_config_panel(monkeypatch, services=["efs"])
        assert "8 regions × 1 service" in text
        assert "4 services" not in text

    def test_counts_follow_the_actual_work_below_the_caps(
        self, monkeypatch: Any
    ) -> None:
        text = render_config_panel(
            monkeypatch,
            services=["ec2", "s3", "efs"],
            region_list=["eu-central-1", "us-east-1"],
        )
        assert "2 regions × 3 services" in text

    def test_caps_still_bound_large_work(self, monkeypatch: Any) -> None:
        regions = [f"region-{i}" for i in range(12)]
        services = ["ec2", "s3", "ecs", "efs", "elb", "vpc", "rds", "autoscaling"]
        text = render_config_panel(monkeypatch, services=services, region_list=regions)
        assert "8 regions × 4 services" in text

    def test_singular_grammar_for_one_region_and_one_service(
        self, monkeypatch: Any
    ) -> None:
        text = render_config_panel(
            monkeypatch, services=["efs"], region_list=["eu-central-1"]
        )
        assert "1 region × 1 service" in text
        assert "1 regions" not in text
        assert "1 services" not in text

    def test_tag_mode_has_no_services_multiplier(self, monkeypatch: Any) -> None:
        # Resource Groups API fans out per region only.
        text = render_config_panel(
            monkeypatch,
            tag_key="managed_by",
            tag_value="terraform",
            region_list=["eu-central-1", "us-east-1"],
        )
        assert "2 regions" in text
        assert "service" not in text.split("Tag Filter")[0].split("Workers")[1]

    def test_all_services_mode_has_no_services_multiplier(
        self, monkeypatch: Any
    ) -> None:
        text = render_config_panel(
            monkeypatch,
            all_services=True,
            tag_key="managed_by",
            region_list=["eu-central-1"],
        )
        assert "1 region" in text
        assert "×" not in text
