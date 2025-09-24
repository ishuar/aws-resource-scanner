"""
S3 Service Scanner
-----------------

Handles scanning of S3 resources including buckets.
"""

from typing import Any, Dict, List, Optional

import botocore
from rich.console import Console

console = Console()


def scan_s3(
    session: Any,
    region: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> Dict[str, Any]:
    """Scan S3 resources in the specified region with optimized API filtering and pagination."""
    s3_client = session.client("s3", region_name=region)
    result = {}
    try:
        # S3 buckets with pagination (S3 doesn't support server-side tag filtering for list_buckets)
        buckets = []
        paginator = s3_client.get_paginator("list_buckets")
        page_iterator = paginator.paginate()

        for page in page_iterator:
            buckets.extend(page.get("Buckets", []))

        # Filter buckets by tags (must be done client-side)
        filtered_buckets = []
        for bucket in buckets:
            try:
                # Get bucket location to ensure we're only processing buckets in the target region
                location_response = s3_client.get_bucket_location(Bucket=bucket["Name"])
                bucket_region = location_response.get("LocationConstraint")

                # Handle special case for us-east-1
                if bucket_region is None:
                    bucket_region = "us-east-1"

                # Only process buckets in the target region
                if bucket_region == region:
                    if tag_key and tag_value:
                        # Check bucket tags
                        try:
                            tags_response = s3_client.get_bucket_tagging(
                                Bucket=bucket["Name"]
                            )
                            tags = tags_response.get("TagSet", [])

                            if any(
                                t["Key"] == tag_key and t["Value"] == tag_value
                                for t in tags
                            ):
                                bucket["tags"] = tags
                                filtered_buckets.append(bucket)
                        except botocore.exceptions.ClientError as e:
                            # Bucket has no tags or access denied
                            if e.response["Error"]["Code"] != "NoSuchTagSet":
                                console.print(
                                    f"[yellow]Could not get tags for bucket {bucket['Name']}: {e}[/yellow]"
                                )
                    else:
                        # No tag filtering, include all buckets in region
                        try:
                            tags_response = s3_client.get_bucket_tagging(
                                Bucket=bucket["Name"]
                            )
                            bucket["tags"] = tags_response.get("TagSet", [])
                        except botocore.exceptions.ClientError:
                            bucket["tags"] = []
                        filtered_buckets.append(bucket)

            except botocore.exceptions.ClientError as e:
                console.print(
                    f"[yellow]Could not process bucket {bucket['Name']}: {e}[/yellow]"
                )

        result["buckets"] = filtered_buckets

    except botocore.exceptions.BotoCoreError as e:
        console.print(f"[red]S3 scan failed: {e}[/red]")
    return result


def process_s3_output(
    service_data: Dict[str, Any], region: str, flattened_resources: List[Dict[str, Any]]
) -> None:
    """Process S3 scan results for output formatting."""
    for bucket in service_data.get("buckets", []):
        bucket_name = bucket.get("Name", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": bucket_name,
                "resource_family": "s3",
                "resource_type": "bucket",
                "resource_id": bucket_name,
                "resource_arn": f"arn:aws:s3:::{bucket_name}",
            }
        )
