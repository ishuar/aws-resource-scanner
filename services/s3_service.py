"""
S3 Service Scanner
-----------------

Handles scanning of S3 resources including buckets.
? Documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from botocore.exceptions import BotoCoreError, ClientError

from aws_scanner_lib.logging import get_logger, get_output_console

# Service logger
logger = get_logger("s3_service")

# Separate console for user output to avoid interfering with logs and progress bars
output_console = get_output_console()

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
                logger.warning("Could not get tags for bucket %s: %s", bucket_name, e)
                tags = []

        bucket["tags"] = tags

        # Return all buckets in the target region (no tag filtering)
        return bucket

    except ClientError as e:
        logger.warning("Could not process bucket %s: %s", bucket['Name'], e)
        return None


def scan_s3(
    session: Any,
    region: str,
) -> Dict[str, Any]:
    """Scan all S3 resources in the specified region without tag filtering."""
    logger.debug("Starting S3 service scan in region %s", region)

    # Show progress to user on separate console (will not conflict with logging or progress bars)
    if logger.is_debug_enabled():
        output_console.print(f"[blue]Scanning S3 resources in {region}[/blue]")

    logger.log_aws_operation("s3", "describe_buckets", region, parallel_workers=S3_MAX_WORKERS)

    s3_client = session.client("s3", region_name=region)
    result = {}
    try:
        # S3 buckets with pagination
        with logger.timer(f"S3 list buckets in {region}"):
            buckets = []
            paginator = s3_client.get_paginator("list_buckets")
            page_iterator = paginator.paginate()

            for page in page_iterator:
                buckets.extend(page.get("Buckets", []))

            logger.debug("Retrieved %d total buckets from S3 list_buckets API", len(buckets))

        # Process buckets in parallel for much better performance
        filtered_buckets = []

        # Use ThreadPoolExecutor to parallelize bucket processing
        with logger.timer(f"S3 parallel bucket processing in {region}"):
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
                        logger.warning("Error processing bucket %s: %s", bucket.get('Name', 'unknown'), e)

            logger.debug("Processed %d buckets in region %s, %d matched region filter",
                        len(buckets), region, len(filtered_buckets))

        result["buckets"] = filtered_buckets

    except BotoCoreError as e:
        logger.error("S3 scan failed in region %s: %s", region, str(e))
        logger.log_error_context(e, {"region": region, "operation": "s3_scan"})

    # Log completion with resource count
    total_resources = sum(len(result.get(key, [])) for key in result.keys())
    logger.info("S3 scan completed in region %s: %d total resources", region, total_resources)

    # Debug-level details about each resource type
    for resource_type, resources in result.items():
        if resources:
            logger.debug("S3 %s in %s: %d resources", resource_type, region, len(resources))

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
                "resource_type": "s3:bucket",
                "resource_id": bucket_name,
                "resource_arn": f"arn:aws:s3:::{bucket_name}",
            }
        )
