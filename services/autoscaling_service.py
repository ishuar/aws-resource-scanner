"""
Auto Scaling Service Scanner
---------------------------

Handles scanning of Auto Scaling resources including auto scaling groups,
launch configurations, and launch templates with optional tag filtering.
? Documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/autoscaling.html

"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from botocore.exceptions import BotoCoreError, ClientError

from aws_scanner_lib.logging import get_logger, get_output_console

# Service logger
logger = get_logger("autoscaling_service")

# Separate console for user output to avoid interfering with logs and progress bars
output_console = get_output_console()

# AutoScaling operations can be parallelized for better performance
AUTOSCALING_MAX_WORKERS = 3  # Parallel workers for different resource types


def _scan_asg_parallel(
    autoscaling_client: Any,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Scan Auto Scaling Groups in parallel with optional tag filtering."""
    asgs = []
    try:
        paginator = autoscaling_client.get_paginator("describe_auto_scaling_groups")
        for page in paginator.paginate():
            for asg in page["AutoScalingGroups"]:
                # Apply tag filtering if specified
                if tag_key and tag_value:
                    # Both tag_key and tag_value specified - must match exactly
                    if not any(
                        t.get("Key") == tag_key and t.get("Value") == tag_value
                        for t in asg.get("Tags", [])
                    ):
                        continue
                elif tag_key:
                    # Only tag_key specified - key must exist (any value)
                    if not any(t.get("Key") == tag_key for t in asg.get("Tags", [])):
                        continue
                elif tag_value:
                    # Only tag_value specified - value must exist (any key)
                    if not any(
                        t.get("Value") == tag_value for t in asg.get("Tags", [])
                    ):
                        continue
                # If no tag filters or tag matches, include the ASG
                asgs.append(asg)
    except (ClientError, BotoCoreError) as e:
        logger.warning("Failed to scan Auto Scaling Groups: %s", str(e))
    return asgs


def _scan_launch_configurations_parallel(
    autoscaling_client: Any, matching_lc_names: List[str]
) -> List[Dict[str, Any]]:
    """Scan Launch Configurations in parallel, filtered by matching launch configuration names."""
    launch_configs: List[Dict[str, Any]] = []
    if not matching_lc_names:
        # If no ASGs match the tag filter, don't return any launch configurations
        return launch_configs

    try:
        paginator = autoscaling_client.get_paginator("describe_launch_configurations")
        for page in paginator.paginate():
            for lc in page["LaunchConfigurations"]:
                # Only include launch configurations that are referenced by matching ASGs
                if lc.get("LaunchConfigurationName") in matching_lc_names:
                    launch_configs.append(lc)
    except (ClientError, BotoCoreError) as e:
        logger.warning("Failed to scan Launch Configurations: %s", str(e))
    return launch_configs


def _scan_launch_templates_parallel(
    ec2_client: Any, tag_key: Optional[str] = None, tag_value: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Scan Launch Templates in parallel with optional tag filtering."""
    launch_templates = []
    try:
        paginator = ec2_client.get_paginator("describe_launch_templates")
        for page in paginator.paginate():
            for template in page["LaunchTemplates"]:
                # Apply tag filtering if specified
                if tag_key and tag_value:
                    # Both tag_key and tag_value specified - must match exactly
                    if not any(
                        t.get("Key") == tag_key and t.get("Value") == tag_value
                        for t in template.get("Tags", [])
                    ):
                        continue
                elif tag_key:
                    # Only tag_key specified - key must exist (any value)
                    if not any(
                        t.get("Key") == tag_key for t in template.get("Tags", [])
                    ):
                        continue
                elif tag_value:
                    # Only tag_value specified - value must exist (any key)
                    if not any(
                        t.get("Value") == tag_value for t in template.get("Tags", [])
                    ):
                        continue
                # If no tag filters or tag matches, include the template
                launch_templates.append(template)
    except (ClientError, BotoCoreError) as e:
        logger.warning("Failed to scan Launch Templates: %s", str(e))
    return launch_templates


def scan_autoscaling(
    session: Any,
    region: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> Dict[str, Any]:
    """Scan Auto Scaling resources in the specified region comprehensively using parallel processing with optional tag filtering."""
    logger.debug("Starting Auto Scaling scan in region %s", region)
    if tag_key or tag_value:
        logger.debug("Applying tag filters - key: %s, value: %s", tag_key, tag_value)

    # Show progress to user on separate console (will not conflict with logging or progress bars)
    if logger.is_debug_enabled():
        output_console.print(
            f"[blue]Scanning Auto Scaling resources in {region}[/blue]"
        )

    logger.log_aws_operation(
        "autoscaling",
        "describe_multiple",
        region,
        parallel_workers=AUTOSCALING_MAX_WORKERS,
    )

    autoscaling_client = session.client("autoscaling", region_name=region)
    ec2_client = session.client("ec2", region_name=region)
    result = {}

    try:
        # Use ThreadPoolExecutor to parallelize AutoScaling resource scanning
        with logger.timer(f"Auto Scaling parallel scan in {region}"):
            with ThreadPoolExecutor(max_workers=AUTOSCALING_MAX_WORKERS) as executor:
                # Submit tasks for parallel execution with tag filtering
                asgs_future = executor.submit(
                    _scan_asg_parallel, autoscaling_client, tag_key, tag_value
                )
                launch_templates_future = executor.submit(
                    _scan_launch_templates_parallel, ec2_client, tag_key, tag_value
                )

                # Collect Auto Scaling Groups results first
                try:
                    result["auto_scaling_groups"] = asgs_future.result()
                    logger.debug(
                        "Found %d Auto Scaling Groups",
                        len(result["auto_scaling_groups"]),
                    )
                except (ClientError, BotoCoreError) as e:
                    logger.warning(
                        "Failed to scan Auto Scaling Groups in %s: %s", region, str(e)
                    )
                    result["auto_scaling_groups"] = []

                # Extract launch configuration names from matching ASGs
                launch_config_names = []
                for asg in result["auto_scaling_groups"]:
                    lc_name = asg.get("LaunchConfigurationName")
                    if lc_name:
                        launch_config_names.append(lc_name)

                # Now scan launch configurations if needed
                if launch_config_names:
                    launch_configs_future = executor.submit(
                        _scan_launch_configurations_parallel,
                        autoscaling_client,
                        launch_config_names,
                    )
                    try:
                        result["launch_configurations"] = launch_configs_future.result()
                        logger.debug(
                            "Found %d Launch Configurations",
                            len(result["launch_configurations"]),
                        )
                    except (ClientError, BotoCoreError) as e:
                        logger.warning(
                            "Failed to scan Launch Configurations in %s: %s",
                            region,
                            str(e),
                        )
                        result["launch_configurations"] = []
                else:
                    result["launch_configurations"] = []

                # Collect Launch Templates results
                try:
                    result["launch_templates"] = launch_templates_future.result()
                    logger.debug(
                        "Found %d Launch Templates", len(result["launch_templates"])
                    )
                except (ClientError, BotoCoreError) as e:
                    logger.warning(
                        "Failed to scan Launch Templates in %s: %s", region, str(e)
                    )
                    result["launch_templates"] = []

    except BotoCoreError as e:
        logger.error("Auto Scaling scan failed in %s: %s", region, str(e))
        logger.log_error_context(
            e, {"service": "autoscaling", "region": region, "operation": "full_scan"}
        )
        result = {
            "auto_scaling_groups": [],
            "launch_configurations": [],
            "launch_templates": [],
        }

    total_resources = (
        len(result.get("auto_scaling_groups", []))
        + len(result.get("launch_configurations", []))
        + len(result.get("launch_templates", []))
    )

    logger.info(
        "Auto Scaling scan completed in %s: %d total resources", region, total_resources
    )

    # Debug-level details about each resource type
    for resource_type, resources in result.items():
        if resources:
            logger.debug(
                "Auto Scaling %s in %s: %d resources",
                resource_type,
                region,
                len(resources),
            )

    return result


def process_autoscaling_output(
    service_data: Dict[str, Any], region: str, flattened_resources: List[Dict[str, Any]]
) -> None:
    """Process Auto Scaling scan results for output formatting."""
    # Auto Scaling Groups
    for asg in service_data.get("auto_scaling_groups", []):
        asg_name = asg.get("AutoScalingGroupName", "N/A")
        asg_arn = asg.get("AutoScalingGroupARN", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": asg_name,
                "resource_type": "autoscaling:auto_scaling_group",
                "resource_id": asg_name,
                "resource_arn": asg_arn,
            }
        )

    # Launch Configurations
    for lc in service_data.get("launch_configurations", []):
        lc_name = lc.get("LaunchConfigurationName", "N/A")
        lc_arn = lc.get("LaunchConfigurationARN", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": lc_name,
                "resource_type": "autoscaling:launch_configuration",
                "resource_id": lc_name,
                "resource_arn": lc_arn,
            }
        )

    # Launch Templates
    for lt in service_data.get("launch_templates", []):
        lt_name = lt.get("LaunchTemplateName", "N/A")
        lt_id = lt.get("LaunchTemplateId", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": lt_name,
                "resource_type": "autoscaling:launch_template",
                "resource_id": lt_id,
                "resource_arn": "N/A",  # Launch Templates do not have ARNs
            }
        )
