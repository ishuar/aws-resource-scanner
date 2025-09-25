"""
S3 Service Scanner
-----------------

Handles scanning of S3 resources including buckets.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from botocore.exceptions import BotoCoreError, ClientError
from rich.console import Console

console = Console()

# S3 operations can be parallelized for better performance
# Using 6 workers to balance speed with AWS API rate limits
S3_MAX_WORKERS = 6


def _process_bucket_parallel(
    s3_client: Any,
    bucket: Dict[str, Any],
    region: str,
) -> Optional[Dict[str, Any]]:
    """Process a single bucket in parallel - check region only."""
    try:
        bucket_name = bucket["Name"]

        # Get bucket location to ensure we're only processing buckets in the target region
        location_response = s3_client.get_bucket_location(Bucket=bucket_name)
        bucket_region = location_response.get("LocationConstraint")

        # Handle special case for us-east-1
        if bucket_region is None:
            bucket_region = "us-east-1"

        # Only process buckets in the target region
        if bucket_region != region:
            return None

        # Get bucket tags for metadata (but no filtering)
        try:
            tags_response = s3_client.get_bucket_tagging(Bucket=bucket_name)
            tags = tags_response.get("TagSet", [])
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchTagSet":
                tags = []
            else:
                console.print(
                    f"[yellow]Could not get tags for bucket {bucket_name}: {e}[/yellow]"
                )
                tags = []

        bucket["tags"] = tags

        # Return all buckets in the target region (no tag filtering)
        return bucket

    except ClientError as e:
        console.print(
            f"[yellow]Could not process bucket {bucket['Name']}: {e}[/yellow]"
        )
        return None


def scan_s3(
    session: Any,
    region: str,
) -> Dict[str, Any]:
    """Scan all S3 resources in the specified region without tag filtering."""
    s3_client = session.client("s3", region_name=region)
    result = {}
    try:
        # S3 buckets with pagination
        buckets = []
        paginator = s3_client.get_paginator("list_buckets")
        page_iterator = paginator.paginate()

        for page in page_iterator:
            buckets.extend(page.get("Buckets", []))

        # Process buckets in parallel for much better performance
        filtered_buckets = []

        # Use ThreadPoolExecutor to parallelize bucket processing
        with ThreadPoolExecutor(max_workers=S3_MAX_WORKERS) as executor:
            # Submit all bucket processing tasks (no tag filtering)
            future_to_bucket = {
                executor.submit(
                    _process_bucket_parallel,
                    s3_client,
                    bucket,
                    region,
                ): bucket
                for bucket in buckets
            }

            # Collect results as they complete
            for future in as_completed(future_to_bucket):
                try:
                    result_bucket = future.result()
                    if result_bucket is not None:
                        filtered_buckets.append(result_bucket)
                except (ClientError, BotoCoreError) as e:
                    bucket = future_to_bucket[future]
                    console.print(
                        f"[yellow]Error processing bucket {bucket.get('Name', 'unknown')}: {e}[/yellow]"
                    )

        result["buckets"] = filtered_buckets

    except BotoCoreError as e:
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
                "resource_type": "s3:bucket",
                "resource_id": bucket_name,
                "resource_arn": f"arn:aws:s3:::{bucket_name}",
            }
        )
