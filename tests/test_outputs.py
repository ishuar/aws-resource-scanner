"""
Output seam: aws_scanner_lib.outputs.output_results and the markdown report.

output_results is the single funnel from nested scan results to files on
disk. These tests pin: format routing, which files get written, the return
value, and how results from the two scan paths (traditional vs Resource
Groups API) are routed to processors.
"""

import json
from pathlib import Path
from typing import Any, Dict

from aws_scanner_lib.outputs import (
    compare_with_existing,
    generate_markdown_summary,
    output_results,
)

REGION = "eu-central-1"


def traditional_results() -> Dict[str, Any]:
    """Nested results as scan_region produces them (traditional path)."""
    return {
        REGION: {
            "s3": {"buckets": [{"Name": "bucket-a"}, {"Name": "bucket-b"}]},
            "ec2": {"instances": [{"InstanceId": "i-1", "Tags": []}]},
        }
    }


def resource_groups_results() -> Dict[str, Any]:
    """Nested results as the Resource Groups API path produces them."""
    return {
        REGION: {
            "lambda": {
                "functions": [
                    {
                        "ResourceARN": "arn:aws:lambda:eu-central-1:1:function:fn",
                        "ResourceId": "fn",
                        "ResourceType": "lambda:function",
                        "Region": REGION,
                        "Tags": [{"Key": "env", "Value": "prod"}],
                    }
                ]
            }
        }
    }


class TestOutputResults:
    def test_json_writes_the_flattened_list_and_returns_the_count(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "scan.json"
        count = output_results(traditional_results(), out, "json", debug=False)

        assert count == 3
        written = json.loads(out.read_text())
        assert len(written) == 3
        assert {r["resource_type"] for r in written} == {"s3:bucket", "ec2:instance"}

    def test_table_format_still_writes_the_json_file(self, tmp_path: Path) -> None:
        out = tmp_path / "scan.json"
        count = output_results(traditional_results(), out, "table", debug=False)

        assert count == 3
        assert json.loads(out.read_text())

    def test_markdown_format_writes_a_md_file_with_the_md_suffix(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "scan.json"
        count = output_results(traditional_results(), out, "md", debug=False)

        assert count == 3
        md_file = tmp_path / "scan.md"
        assert md_file.exists()
        assert "# AWS Resources Scan Report" in md_file.read_text()

    def test_markdown_alias_behaves_like_md(self, tmp_path: Path) -> None:
        out = tmp_path / "scan.json"
        output_results(traditional_results(), out, "markdown", debug=False)
        assert (tmp_path / "scan.md").exists()

    def test_unknown_format_writes_nothing_but_still_returns_the_count(
        self, tmp_path: Path
    ) -> None:
        # Characterization: an unknown format is reported on the console
        # only — no file, no exception, count still returned. (A future
        # change may make this a hard error; that would be an improvement.)
        out = tmp_path / "scan.json"
        count = output_results(traditional_results(), out, "yaml", debug=False)

        assert count == 3
        assert not out.exists()

    def test_missing_output_directory_is_created(self, tmp_path: Path) -> None:
        out = tmp_path / "deeply" / "nested" / "scan.json"
        output_results(traditional_results(), out, "json", debug=False)
        assert out.exists()

    def test_empty_results_produce_an_empty_file_and_zero(self, tmp_path: Path) -> None:
        out = tmp_path / "scan.json"
        count = output_results({}, out, "json", debug=False)

        assert count == 0
        assert json.loads(out.read_text()) == []

    def test_empty_service_data_is_skipped(self, tmp_path: Path) -> None:
        out = tmp_path / "scan.json"
        count = output_results({REGION: {"ec2": {}}}, out, "json", debug=False)
        assert count == 0

    def test_resource_groups_data_routes_to_the_generic_processor(
        self, tmp_path: Path
    ) -> None:
        # A service with no dedicated processor (lambda) must still land in
        # the output — via the generic processor, keyed by its ResourceType.
        out = tmp_path / "scan.json"
        count = output_results(resource_groups_results(), out, "json", debug=False)

        assert count == 1
        written = json.loads(out.read_text())
        assert written[0]["resource_type"] == "lambda:function"
        assert written[0]["resource_id"] == "fn"

    def test_resource_groups_data_under_a_known_service_name_still_goes_generic(
        self, tmp_path: Path
    ) -> None:
        # Characterization of the structural sniffing: even under the "ec2"
        # key, Resource-Groups-shaped records bypass process_ec2_output.
        # The planned typed-Resource refactor replaces sniffing with an
        # explicit source marker — behaviour must stay identical.
        results = {
            REGION: {
                "ec2": {
                    "instances": [
                        {
                            "ResourceARN": "arn:aws:ec2:eu-central-1:1:instance/i-7",
                            "ResourceId": "i-7",
                            "ResourceType": "ec2:instance",
                        }
                    ]
                }
            }
        }
        out = tmp_path / "scan.json"
        count = output_results(results, out, "json", debug=False)

        assert count == 1
        record = json.loads(out.read_text())[0]
        # The generic processor keeps the real ARN; process_ec2_output
        # would have hardcoded resource_arn to "N/A".
        assert record["resource_arn"] == "arn:aws:ec2:eu-central-1:1:instance/i-7"

    def test_unknown_traditional_service_falls_back_to_generic(
        self, tmp_path: Path
    ) -> None:
        results = {REGION: {"unknownsvc": {"things": [{"SomeKey": "some-value"}]}}}
        out = tmp_path / "scan.json"
        count = output_results(results, out, "json", debug=False)

        assert count == 1
        record = json.loads(out.read_text())[0]
        # Nothing extractable: identity fields degrade to N/A, not a crash.
        assert record["resource_id"] == "N/A"
        assert record["resource_arn"] == "N/A"


class TestCompareWithExisting:
    """--compare diffs a new scan against the JSON file a previous scan wrote."""

    def test_identical_rescan_reports_no_changes(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        out = tmp_path / "scan.json"
        output_results(traditional_results(), out, "json", debug=False)
        capsys.readouterr()  # discard output_results noise

        compare_with_existing(out, traditional_results())

        assert "No changes detected" in capsys.readouterr().out

    def test_changed_scan_reports_changes(self, tmp_path: Path, capsys: Any) -> None:
        out = tmp_path / "scan.json"
        output_results(traditional_results(), out, "json", debug=False)
        capsys.readouterr()

        changed = traditional_results()
        changed[REGION]["s3"]["buckets"].append({"Name": "bucket-new"})
        compare_with_existing(out, changed)

        assert "Changes detected" in capsys.readouterr().out

    def test_missing_file_is_a_quiet_no_op(self, tmp_path: Path, capsys: Any) -> None:
        compare_with_existing(tmp_path / "never-written.json", traditional_results())
        captured = capsys.readouterr().out
        assert "Changes detected" not in captured
        assert "No changes detected" not in captured


class TestMarkdownSummary:
    def test_report_counts_by_region_service_and_type(self) -> None:
        flattened = [
            {
                "region": REGION,
                "resource_name": "bucket-a",
                "resource_type": "s3:bucket",
                "resource_id": "bucket-a",
                "resource_arn": "arn:aws:s3:::bucket-a",
            },
            {
                "region": "us-east-1",
                "resource_type": "ec2:instance",
                "resource_id": "i-1",
                "resource_arn": "N/A",
            },
        ]
        report = generate_markdown_summary(flattened, {})

        assert "**Total Resources:** 2" in report
        assert f"- **{REGION}**: 1 resources" in report
        assert "- **us-east-1**: 1 resources" in report
        assert "- **S3**: 1 resources" in report
        assert "- **EC2**: 1 resources" in report
        assert "- **s3:bucket**: 1" in report

    def test_missing_resource_name_falls_back_to_the_id(self) -> None:
        flattened = [
            {
                "region": REGION,
                "resource_type": "ecs:cluster",
                "resource_id": "prod-cluster",
                "resource_arn": "arn:aws:ecs:eu-central-1:1:cluster/prod-cluster",
            }
        ]
        report = generate_markdown_summary(flattened, {})
        assert "| prod-cluster |" in report

    def test_pipes_in_values_are_escaped_so_tables_stay_valid(self) -> None:
        flattened = [
            {
                "region": REGION,
                "resource_name": "name|with|pipes",
                "resource_type": "s3:bucket",
                "resource_id": "name|with|pipes",
                "resource_arn": "arn:aws:s3:::name|with|pipes",
            }
        ]
        report = generate_markdown_summary(flattened, {})
        assert "name\\|with\\|pipes" in report
