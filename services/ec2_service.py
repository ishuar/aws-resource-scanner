"""
EC2 Service Scanner
------------------

Handles scanning of EC2 resources including instances, volumes, security groups, AMIs, and snapshots.
Prioritizes Resource Groups Tagging API for efficient server-side filtering when tags are available.
Documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from botocore.exceptions import BotoCoreError, ClientError

from aws_scanner_lib.logging import get_logger, get_output_console

# Service logger
logger = get_logger("ec2_service")

# Separate console for user output to avoid interfering with logs and progress bars
output_console = get_output_console()

# EC2 operations can be parallelized for better performance
EC2_MAX_WORKERS = 5  # Parallel workers for different resource types


def _scan_ec2_instances(
    ec2_client: Any, filters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Scan EC2 instances in parallel."""
    instances = []
    paginator = ec2_client.get_paginator("describe_instances")
    page_iterator = (
        paginator.paginate(Filters=filters) if filters else paginator.paginate()
    )

    for page in page_iterator:
        for reservation in page["Reservations"]:
            instances.extend(reservation["Instances"])
    return instances


def _scan_ec2_volumes(
    ec2_client: Any, filters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Scan EC2 volumes in parallel."""
    volumes = []
    paginator = ec2_client.get_paginator("describe_volumes")
    page_iterator = (
        paginator.paginate(Filters=filters) if filters else paginator.paginate()
    )

    for page in page_iterator:
        volumes.extend(page["Volumes"])
    return volumes


def _scan_ec2_security_groups(
    ec2_client: Any, filters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Scan EC2 security groups in parallel."""
    security_groups = []
    paginator = ec2_client.get_paginator("describe_security_groups")
    page_iterator = (
        paginator.paginate(Filters=filters) if filters else paginator.paginate()
    )

    for page in page_iterator:
        security_groups.extend(page["SecurityGroups"])
    return security_groups


def _scan_ec2_amis(ec2_client: Any) -> List[Dict[str, Any]]:
    """Scan EC2 AMIs without tag filtering."""
    amis = []
    try:
        paginator = ec2_client.get_paginator("describe_images")
        page_iterator = paginator.paginate(Owners=["self"])

        for page in page_iterator:
            amis.extend(page["Images"])
    except (ClientError, BotoCoreError):
        # Fallback to non-paginated call if paginator fails
        amis_response = ec2_client.describe_images(Owners=["self"])
        amis.extend(amis_response["Images"])
    return amis


def _scan_ec2_snapshots(ec2_client: Any) -> List[Dict[str, Any]]:
    """Scan EC2 snapshots without tag filtering."""
    snapshots = []
    try:
        paginator = ec2_client.get_paginator("describe_snapshots")
        page_iterator = paginator.paginate(OwnerIds=["self"])

        for page in page_iterator:
            snapshots.extend(page["Snapshots"])
    except (ClientError, BotoCoreError):
        # Fallback to non-paginated call if paginator fails
        snapshots_response = ec2_client.describe_snapshots(OwnerIds=["self"])
        snapshots.extend(snapshots_response["Snapshots"])
    return snapshots


def scan_ec2(
    session: Any,
    region: str,
) -> Dict[str, Any]:
    """
    Scan all EC2 resources using describe APIs without tag filtering.

    Tag-based filtering is handled by the Resource Groups API at the main scanner level.
    """
    logger.debug("Starting EC2 service scan in region %s", region)

    # Show progress to user on separate console (will not conflict with logging or progress bars)
    # Show progress only in debug mode to avoid interfering with progress bars
    if logger.is_debug_enabled():
        output_console.print(f"[blue]Scanning EC2 resources in {region}[/blue]")

    logger.log_aws_operation("ec2", "describe_multiple", region, parallel_workers=EC2_MAX_WORKERS)

    result = {}
    ec2_client = session.client("ec2", region_name=region)

    try:
        # Empty filters - get all resources in the region
        filters: List[Dict[str, Any]] = []

        # Use ThreadPoolExecutor to parallelize resource scanning
        with logger.timer(f"EC2 parallel scan in {region}"):
            with ThreadPoolExecutor(max_workers=EC2_MAX_WORKERS) as executor:
                # Submit all tasks
                instances_future = executor.submit(_scan_ec2_instances, ec2_client, filters)
                volumes_future = executor.submit(_scan_ec2_volumes, ec2_client, filters)
                security_groups_future = executor.submit(
                    _scan_ec2_security_groups, ec2_client, filters
                )
                amis_future = executor.submit(_scan_ec2_amis, ec2_client)
                snapshots_future = executor.submit(_scan_ec2_snapshots, ec2_client)

        # Collect results in the expected dictionary structure
        try:
            result["instances"] = instances_future.result()
        except (ClientError, BotoCoreError) as e:
            logger.warning("Failed to scan EC2 instances in region %s: %s", region, str(e))
            result["instances"] = []

        try:
            result["volumes"] = volumes_future.result()
        except (ClientError, BotoCoreError) as e:
            logger.warning("Failed to scan EC2 volumes in region %s: %s", region, str(e))
            result["volumes"] = []

        try:
            result["security_groups"] = security_groups_future.result()
        except (ClientError, BotoCoreError) as e:
            logger.warning("Failed to scan EC2 security groups in region %s: %s", region, str(e))
            result["security_groups"] = []

        try:
            result["amis"] = amis_future.result()
        except (ClientError, BotoCoreError) as e:
            logger.warning("Failed to scan EC2 AMIs in region %s: %s", region, str(e))
            result["amis"] = []

        try:
            result["snapshots"] = snapshots_future.result()
        except (ClientError, BotoCoreError) as e:
            logger.warning("Failed to scan EC2 snapshots in region %s: %s", region, str(e))
            result["snapshots"] = []

    except (ClientError, BotoCoreError) as e:
        logger.error("EC2 scan failed for region %s: %s", region, str(e))
        logger.log_error_context(e, {"service": "ec2", "region": region, "operation": "full_scan"})
        result = {
            "instances": [],
            "volumes": [],
            "security_groups": [],
            "amis": [],
            "snapshots": [],
        }

        # Log scan completion with resource counts
    total_resources = sum(len(v) for v in result.values())
    logger.info("EC2 scan completed in region %s: %d total resources", region, total_resources)

    # Debug-level details about each resource type
    for resource_type, resources in result.items():
        if resources:
            logger.debug("EC2 %s in %s: %d resources", resource_type, region, len(resources))

    return result


def process_ec2_output(
    service_data: Dict[str, Any], region: str, flattened_resources: List[Dict[str, Any]]
) -> None:
    """Process EC2 scan results for output formatting."""
    # EC2 Instances
    for instance in service_data.get("instances", []):
        instance_id = instance.get("InstanceId", "N/A")
        instance_name = "N/A"
        # Try to get Name tag
        for tag in instance.get("Tags", []):
            if tag["Key"] == "Name":
                instance_name = tag["Value"]
                break
        if instance_name == "N/A":
            instance_name = instance_id

        flattened_resources.append(
            {
                "region": region,
                "resource_type": "ec2:instance",  # Unified format: service:type
                "resource_id": instance_id,
                "resource_arn": "N/A",  # Instances don't have ARNs in AWS API
            }
        )

    # EBS Volumes
    for volume in service_data.get("volumes", []):
        volume_id = volume.get("VolumeId", "N/A")
        volume_name = "N/A"
        # Try to get Name tag
        for tag in volume.get("Tags", []):
            if tag["Key"] == "Name":
                volume_name = tag["Value"]
                break
        if volume_name == "N/A":
            volume_name = volume_id

        flattened_resources.append(
            {
                "region": region,
                "resource_name": volume_name,
                "resource_type": "ec2:volume",
                "resource_id": volume_id,
                "resource_arn": "N/A",  # Volumes don't have ARNs in AWS API
            }
        )

    # Security Groups
    for sg in service_data.get("security_groups", []):
        sg_id = sg.get("GroupId", "N/A")
        sg_name = sg.get("GroupName", sg_id)

        flattened_resources.append(
            {
                "region": region,
                "resource_name": sg_name,
                "resource_type": "ec2:security_group",
                "resource_id": sg_id,
                "resource_arn": "N/A",  # Security groups don't have ARNs in AWS API
            }
        )

    # AMIs
    for ami in service_data.get("amis", []):
        ami_id = ami.get("ImageId", "N/A")
        ami_name = ami.get("Name", ami_id)

        flattened_resources.append(
            {
                "region": region,
                "resource_name": ami_name,
                "resource_type": "ec2:ami",
                "resource_id": ami_id,
                "resource_arn": "N/A",  # AMIs don't have ARNs in AWS API
            }
        )

    # Snapshots
    for snapshot in service_data.get("snapshots", []):
        snapshot_id = snapshot.get("SnapshotId", "N/A")
        snapshot_name = snapshot.get("Description", snapshot_id)

        flattened_resources.append(
            {
                "region": region,
                "resource_name": snapshot_name,
                "resource_type": "ec2:snapshot",
                "resource_id": snapshot_id,
                "resource_arn": "N/A",  # Snapshots don't have ARNs in AWS API
            }
        )
