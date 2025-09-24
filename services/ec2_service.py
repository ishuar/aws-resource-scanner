"""
EC2 Service Scanner
------------------

Handles scanning of EC2 resources including instances, volumes, security groups, AMIs, and snapshots.
"""

from typing import Any, Dict, List, Optional

import botocore
from rich.console import Console

console = Console()


def scan_ec2(
    session: Any,
    region: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> Dict[str, Any]:
    """Scan EC2 resources in the specified region with optimized API filtering and pagination."""
    ec2_client = session.client("ec2", region_name=region)
    result = {}

    # Build AWS API filters for tag filtering
    filters = []
    if tag_key and tag_value:
        filters.append({"Name": f"tag:{tag_key}", "Values": [tag_value]})

    try:
        # Use paginated calls for better performance with large result sets

        # EC2 Instances with API-level filtering
        instances = []
        paginator = ec2_client.get_paginator("describe_instances")
        page_iterator = (
            paginator.paginate(Filters=filters) if filters else paginator.paginate()
        )

        for page in page_iterator:
            for reservation in page["Reservations"]:
                instances.extend(reservation["Instances"])

        # Volumes with API-level filtering
        volumes = []
        paginator = ec2_client.get_paginator("describe_volumes")
        page_iterator = (
            paginator.paginate(Filters=filters) if filters else paginator.paginate()
        )

        for page in page_iterator:
            volumes.extend(page["Volumes"])

        # Security Groups with API-level filtering
        security_groups = []
        paginator = ec2_client.get_paginator("describe_security_groups")
        page_iterator = (
            paginator.paginate(Filters=filters) if filters else paginator.paginate()
        )

        for page in page_iterator:
            security_groups.extend(page["SecurityGroups"])

        # AMIs (owned by self) - Note: tag filtering for AMIs may not work the same way
        amis = []
        try:
            paginator = ec2_client.get_paginator("describe_images")
            page_iterator = paginator.paginate(Owners=["self"])

            for page in page_iterator:
                for ami in page["Images"]:
                    if not filters or any(
                        t.get("Key") == tag_key and t.get("Value") == tag_value
                        for t in ami.get("Tags", [])
                    ):
                        amis.append(ami)
        except Exception:
            # Fallback to non-paginated call if paginator fails
            amis_response = ec2_client.describe_images(Owners=["self"])
            for ami in amis_response["Images"]:
                if not filters or any(
                    t.get("Key") == tag_key and t.get("Value") == tag_value
                    for t in ami.get("Tags", [])
                ):
                    amis.append(ami)

        # Snapshots (owned by self)
        snapshots = []
        try:
            paginator = ec2_client.get_paginator("describe_snapshots")
            page_iterator = paginator.paginate(OwnerIds=["self"])

            for page in page_iterator:
                for snapshot in page["Snapshots"]:
                    if not filters or any(
                        t.get("Key") == tag_key and t.get("Value") == tag_value
                        for t in snapshot.get("Tags", [])
                    ):
                        snapshots.append(snapshot)
        except Exception:
            # Fallback to non-paginated call if paginator fails
            snapshots_response = ec2_client.describe_snapshots(OwnerIds=["self"])
            for snapshot in snapshots_response["Snapshots"]:
                if not filters or any(
                    t.get("Key") == tag_key and t.get("Value") == tag_value
                    for t in snapshot.get("Tags", [])
                ):
                    snapshots.append(snapshot)

        result["instances"] = instances
        result["volumes"] = volumes
        result["security_groups"] = security_groups
        result["amis"] = amis
        result["snapshots"] = snapshots

    except botocore.exceptions.BotoCoreError as e:
        console.print(f"[red]EC2 scan failed: {e}[/red]")
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
