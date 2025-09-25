"""
Resource Groups Tagging API Utility
----------------------------------

Centralized utility for using AWS Resource Groups Tagging API to efficiently
find resources by tags across all AWS services. This provides server-side
filtering that dramatically improves performance compared to client-side filtering.
Supported Services: https://docs.aws.amazon.com/ARG/latest/userguide/supported-resources.html

"""

from typing import Any, Dict, Optional

from botocore.exceptions import BotoCoreError, ClientError
from rich.console import Console

console = Console()


def get_all_tagged_resources_across_services(
    session: Any,
    region: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get ALL resources across ALL AWS services using Resource Groups Tagging API.

    This is the main function for service-agnostic resource discovery.
    It finds resources from ANY AWS service that supports tagging.

    Args:
        session: AWS session object
        region: AWS region name
        tag_key: Tag key to filter by
        tag_value: Tag value to filter by

    Returns:
        Dictionary organized by service with all discovered resources
    """
    if not tag_key and not tag_value:
        console.print(
            "[dim]No tags specified - Resource Groups API requires tags[/dim]"
        )
        return {}

    try:
        console.print(f"\n[dim]🌐 Discovering resources in {region}...[/dim]")

        # Use Resource Groups Tagging API WITHOUT ResourceTypeFilters to get ALL resources
        tagging_client = session.client("resourcegroupstaggingapi", region_name=region)

        tag_filters = []
        if tag_key and tag_value:
            tag_filters.append({"Key": tag_key, "Values": [tag_value]})
        elif tag_key:
            # If only tag_key provided, find all resources with that key (any value)
            tag_filters.append({"Key": tag_key})

        paginator = tagging_client.get_paginator("get_resources")
        page_iterator = paginator.paginate(
            TagFilters=tag_filters
            # NO ResourceTypeFilters - this gets ALL resource types across ALL services
        )

        # Organize resources by service
        service_resources: Dict[str, Any] = {}
        total_resources = 0

        for page in page_iterator:
            for resource in page.get("ResourceTagMappingList", []):
                resource_arn = resource["ResourceARN"]
                tags = resource.get("Tags", [])

                # Extract service and resource type from ARN
                service_name, resource_type = _extract_service_and_type_from_arn(
                    resource_arn
                )

                if service_name:
                    if service_name not in service_resources:
                        service_resources[service_name] = {}

                    if resource_type not in service_resources[service_name]:
                        service_resources[service_name][resource_type] = []

                    # Create comprehensive resource object
                    resource_obj = {
                        "ResourceARN": resource_arn,
                        "ResourceId": _extract_resource_id_from_arn(
                            resource_arn, f"{service_name}:{resource_type}"
                        ),
                        "ResourceType": f"{service_name}:{resource_type}",
                        "Region": region,
                        "Tags": tags,
                        "Service": service_name,
                    }

                    service_resources[service_name][resource_type].append(resource_obj)
                    total_resources += 1

        # Per-region verbose logging removed - overall results shown by main scanner
        return service_resources

    except (ClientError, BotoCoreError) as e:
        console.print(f"[red]❌ Resource Groups API error in {region}: {e}[/red]")
        return {}


def _extract_service_and_type_from_arn(arn: str) -> tuple[str, str]:
    """Extract service name and resource type from an AWS ARN."""
    try:
        # ARN format: arn:aws:service:region:account:resource-type/resource-id
        # or arn:aws:service:region:account:resource-type:resource-id
        parts = arn.split(":")
        if len(parts) >= 6:
            service = parts[2]
            resource_part = parts[5]

            # Handle different resource formats
            if "/" in resource_part:
                resource_type = resource_part.split("/")[0]
            else:
                resource_type = resource_part

            return service, resource_type
    except (IndexError, ValueError):
        pass

    return "", ""


def _extract_resource_id_from_arn(arn: str, resource_type: str) -> Optional[str]:
    """Extract the resource ID from an AWS ARN based on resource type."""
    try:
        if resource_type in ["s3:bucket"]:
            # S3 buckets: arn:aws:s3:::bucket-name
            return arn.split(":::")[-1] if ":::" in arn else None
        elif resource_type.startswith("elasticloadbalancing:"):
            # ELB resources: arn:aws:elasticloadbalancing:region:account:loadbalancer/type/name/id
            # or arn:aws:elasticloadbalancing:region:account:targetgroup/name/id
            parts = arn.split("/")
            if len(parts) >= 2:
                if (
                    resource_type == "elasticloadbalancing:loadbalancer"
                    and len(parts) >= 4
                ):
                    return f"{parts[1]}/{parts[2]}/{parts[3]}"  # type/name/id
                elif (
                    resource_type == "elasticloadbalancing:targetgroup"
                    and len(parts) >= 3
                ):
                    return f"{parts[1]}/{parts[2]}"  # name/id
        elif "/" in arn:
            # Most resources: arn:aws:service:region:account:resource-type/resource-id
            return arn.split("/")[-1]
        else:
            # Some resources use colon separator
            return arn.split(":")[-1]
    except (IndexError, ValueError):
        pass

    return None


def should_use_resource_groups_api(
    tag_key: Optional[str], tag_value: Optional[str]
) -> bool:
    """
    Determine if Resource Groups Tagging API should be used.

    Returns True if either tag_key OR tag_value is provided (prioritize Resource Groups API).
    """
    return bool(tag_key or tag_value)


def scan_all_tagged_resources(
    session: Any,
    region: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> Dict[str, Any]:
    """
    MAIN FUNCTION: Service-agnostic scanning using Resource Groups Tagging API.

    This function finds ALL resources across ALL AWS services that match the tag criteria.
    It returns results in a format compatible with the existing output system.

    Args:
        session: AWS session object
        region: AWS region name
        tag_key: Tag key to filter by
        tag_value: Tag value to filter by

    Returns:
        Dictionary with service names as keys, organized for output compatibility
    """
    if not should_use_resource_groups_api(tag_key, tag_value):
        console.print("[dim]No tags specified for Resource Groups API scan[/dim]")
        return {}

    # Removed verbose logging - handled by main progress bar

    # Get all tagged resources across services
    all_resources = get_all_tagged_resources_across_services(
        session, region, tag_key, tag_value
    )

    if not all_resources:
        return {}

    # Convert to output-compatible format
    output_results: Dict[str, Any] = {}

    for service_name, resource_types in all_resources.items():
        if service_name not in output_results:
            output_results[service_name] = {}

        for resource_type, resources in resource_types.items():
            # Use a consistent naming scheme for resource type keys
            resource_key = (
                f"{resource_type}s"
                if not resource_type.endswith("s")
                else resource_type
            )
            output_results[service_name][resource_key] = resources

    return output_results
