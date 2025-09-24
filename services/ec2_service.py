"""
EC2 Service Scanner
------------------

Handles scanning of EC2 resources including instances, volumes, security groups, AMIs, and snapshots.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from botocore.exceptions import BotoCoreError, ClientError
from rich.console import Console

console = Console()

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


def _scan_ec2_amis(
    ec2_client: Any, tag_key: Optional[str], tag_value: Optional[str]
) -> List[Dict[str, Any]]:
    """Scan EC2 AMIs in parallel."""
    amis = []
    try:
        paginator = ec2_client.get_paginator("describe_images")
        page_iterator = paginator.paginate(Owners=["self"])

        for page in page_iterator:
            for ami in page["Images"]:
                if (
                    not tag_key
                    or not tag_value
                    or any(
                        t.get("Key") == tag_key and t.get("Value") == tag_value
                        for t in ami.get("Tags", [])
                    )
                ):
                    amis.append(ami)
    except (ClientError, BotoCoreError):
        # Fallback to non-paginated call if paginator fails
        amis_response = ec2_client.describe_images(Owners=["self"])
        for ami in amis_response["Images"]:
            if (
                not tag_key
                or not tag_value
                or any(
                    t.get("Key") == tag_key and t.get("Value") == tag_value
                    for t in ami.get("Tags", [])
                )
            ):
                amis.append(ami)
    return amis


def _scan_ec2_snapshots(
    ec2_client: Any, tag_key: Optional[str], tag_value: Optional[str]
) -> List[Dict[str, Any]]:
    """Scan EC2 snapshots in parallel."""
    snapshots = []
    try:
        paginator = ec2_client.get_paginator("describe_snapshots")
        page_iterator = paginator.paginate(OwnerIds=["self"])

        for page in page_iterator:
            for snapshot in page["Snapshots"]:
                if (
                    not tag_key
                    or not tag_value
                    or any(
                        t.get("Key") == tag_key and t.get("Value") == tag_value
                        for t in snapshot.get("Tags", [])
                    )
                ):
                    snapshots.append(snapshot)
    except (ClientError, BotoCoreError):
        # Fallback to non-paginated call if paginator fails
        snapshots_response = ec2_client.describe_snapshots(OwnerIds=["self"])
        for snapshot in snapshots_response["Snapshots"]:
            if (
                not tag_key
                or not tag_value
                or any(
                    t.get("Key") == tag_key and t.get("Value") == tag_value
                    for t in snapshot.get("Tags", [])
                )
            ):
                snapshots.append(snapshot)
    return snapshots


def scan_ec2(
    session: Any,
    region: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> Dict[str, Any]:
    """Scan EC2 resources in a single region using parallel processing."""
    ec2_client = session.client("ec2", region_name=region)
    result = {}

    # Prepare filters for resources that support tag filtering at the API level
    filters = []
    if tag_key and tag_value:
        filters = [{"Name": f"tag:{tag_key}", "Values": [tag_value]}]

    # Use ThreadPoolExecutor to parallelize resource scanning
    with ThreadPoolExecutor(max_workers=EC2_MAX_WORKERS) as executor:
        # Submit all tasks
        instances_future = executor.submit(_scan_ec2_instances, ec2_client, filters)
        volumes_future = executor.submit(_scan_ec2_volumes, ec2_client, filters)
        security_groups_future = executor.submit(
            _scan_ec2_security_groups, ec2_client, filters
        )
        amis_future = executor.submit(_scan_ec2_amis, ec2_client, tag_key, tag_value)
        snapshots_future = executor.submit(
            _scan_ec2_snapshots, ec2_client, tag_key, tag_value
        )

        # Collect results in the expected dictionary structure
        try:
            result["instances"] = instances_future.result()
        except (ClientError, BotoCoreError) as e:
            console.print(
                f"[yellow]Warning: Failed to scan EC2 instances in {region}: {str(e)}[/yellow]"
            )
            result["instances"] = []

        try:
            result["volumes"] = volumes_future.result()
        except (ClientError, BotoCoreError) as e:
            console.print(
                f"[yellow]Warning: Failed to scan EC2 volumes in {region}: {str(e)}[/yellow]"
            )
            result["volumes"] = []

        try:
            result["security_groups"] = security_groups_future.result()
        except (ClientError, BotoCoreError) as e:
            console.print(
                f"[yellow]Warning: Failed to scan EC2 security groups in {region}: {str(e)}[/yellow]"
            )
            result["security_groups"] = []

        try:
            result["amis"] = amis_future.result()
        except (ClientError, BotoCoreError) as e:
            console.print(
                f"[yellow]Warning: Failed to scan EC2 AMIs in {region}: {str(e)}[/yellow]"
            )
            result["amis"] = []

        try:
            result["snapshots"] = snapshots_future.result()
        except (ClientError, BotoCoreError) as e:
            console.print(
                f"[yellow]Warning: Failed to scan EC2 snapshots in {region}: {str(e)}[/yellow]"
            )
            result["snapshots"] = []

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
                "resource_name": instance_name,
                "resource_family": "ec2",
                "resource_type": "instance",
                "resource_id": instance_id,
                "resource_arn": f"arn:aws:ec2:{region}:{instance.get('OwnerId', '')}:instance/{instance_id}",
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
                "resource_family": "ec2",
                "resource_type": "volume",
                "resource_id": volume_id,
                "resource_arn": f"arn:aws:ec2:{region}:{volume.get('OwnerId', '')}:volume/{volume_id}",
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
                "resource_family": "ec2",
                "resource_type": "security_group",
                "resource_id": sg_id,
                "resource_arn": "N/A",  # Security groups don't have ARNs
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
                "resource_family": "ec2",
                "resource_type": "ami",
                "resource_id": ami_id,
                "resource_arn": f"arn:aws:ec2:{region}::image/{ami_id}",
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
                "resource_family": "ec2",
                "resource_type": "snapshot",
                "resource_id": snapshot_id,
                "resource_arn": f"arn:aws:ec2:{region}::snapshot/{snapshot_id}",
            }
        )
