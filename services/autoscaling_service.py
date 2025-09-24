"""
Auto Scaling Service Scanner
---------------------------

Handles scanning of Auto Scaling resources including auto scaling groups,
launch configurations, and launch templates.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from botocore.exceptions import BotoCoreError, ClientError
from rich.console import Console  # pyright: ignore[reportMissingImports]

console = Console()

# AutoScaling operations can be parallelized for better performance
AUTOSCALING_MAX_WORKERS = 3  # Parallel workers for different resource types


def _scan_asg_parallel(
    autoscaling_client: Any, tag_key: Optional[str], tag_value: Optional[str]
) -> List[Dict[str, Any]]:
    """Scan Auto Scaling Groups in parallel."""
    asgs = []
    try:
        paginator = autoscaling_client.get_paginator("describe_auto_scaling_groups")
        for page in paginator.paginate():
            for asg in page["AutoScalingGroups"]:
                if (
                    not tag_key
                    or not tag_value
                    or any(
                        t.get("Key") == tag_key and t.get("Value") == tag_value
                        for t in asg.get("Tags", [])
                    )
                ):
                    asgs.append(asg)
    except (ClientError, BotoCoreError):
        pass
    return asgs


def _scan_launch_configurations_parallel(
    autoscaling_client: Any, tag_key: Optional[str], tag_value: Optional[str]
) -> List[Dict[str, Any]]:
    """Scan Launch Configurations in parallel."""
    launch_configs = []
    try:
        paginator = autoscaling_client.get_paginator("describe_launch_configurations")
        for page in paginator.paginate():
            launch_configs.extend(page["LaunchConfigurations"])
    except (ClientError, BotoCoreError):
        pass
    return launch_configs


def _scan_launch_templates_parallel(
    ec2_client: Any, tag_key: Optional[str], tag_value: Optional[str]
) -> List[Dict[str, Any]]:
    """Scan Launch Templates in parallel."""
    launch_templates = []
    try:
        paginator = ec2_client.get_paginator("describe_launch_templates")
        for page in paginator.paginate():
            for template in page["LaunchTemplates"]:
                if (
                    not tag_key
                    or not tag_value
                    or any(
                        t.get("Key") == tag_key and t.get("Value") == tag_value
                        for t in template.get("Tags", [])
                    )
                ):
                    launch_templates.append(template)
    except (ClientError, BotoCoreError):
        pass
    return launch_templates


def scan_autoscaling(
    session: Any,
    region: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> Dict[str, Any]:
    """Scan Auto Scaling resources in the specified region using parallel processing."""
    autoscaling_client = session.client("autoscaling", region_name=region)
    ec2_client = session.client("ec2", region_name=region)
    result = {}

    try:
        # Use ThreadPoolExecutor to parallelize AutoScaling resource scanning
        with ThreadPoolExecutor(max_workers=AUTOSCALING_MAX_WORKERS) as executor:
            # Submit tasks for parallel execution
            asgs_future = executor.submit(
                _scan_asg_parallel, autoscaling_client, tag_key, tag_value
            )
            launch_configs_future = executor.submit(
                _scan_launch_configurations_parallel,
                autoscaling_client,
                tag_key,
                tag_value,
            )
            launch_templates_future = executor.submit(
                _scan_launch_templates_parallel, ec2_client, tag_key, tag_value
            )

            # Collect Auto Scaling Groups results
            try:
                result["auto_scaling_groups"] = asgs_future.result()
            except (ClientError, BotoCoreError) as e:
                console.print(
                    f"[yellow]Warning: Failed to scan Auto Scaling Groups in {region}: {str(e)}[/yellow]"
                )
                result["auto_scaling_groups"] = []

            # Collect Launch Configurations results
            try:
                all_launch_configs = launch_configs_future.result()
                # Filter launch configs by ASG usage if tag filtering is applied
                if tag_key and tag_value:
                    used_lc_names = {
                        asg.get("LaunchConfigurationName")
                        for asg in result["auto_scaling_groups"]
                        if asg.get("LaunchConfigurationName")
                    }
                    filtered_launch_configs = [
                        lc
                        for lc in all_launch_configs
                        if lc.get("LaunchConfigurationName") in used_lc_names
                    ]
                    result["launch_configurations"] = filtered_launch_configs
                else:
                    result["launch_configurations"] = all_launch_configs
            except (ClientError, BotoCoreError) as e:
                console.print(
                    f"[yellow]Warning: Failed to scan Launch Configurations in {region}: {str(e)}[/yellow]"
                )
                result["launch_configurations"] = []

            # Collect Launch Templates results
            try:
                result["launch_templates"] = launch_templates_future.result()
            except (ClientError, BotoCoreError) as e:
                console.print(
                    f"[yellow]Warning: Failed to scan Launch Templates in {region}: {str(e)}[/yellow]"
                )
                result["launch_templates"] = []

    except BotoCoreError as e:
        console.print(f"[red]Auto Scaling scan failed: {e}[/red]")
        result = {
            "auto_scaling_groups": [],
            "launch_configurations": [],
            "launch_templates": [],
        }

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
                "resource_family": "autoscaling",
                "resource_type": "auto_scaling_group",
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
                "resource_family": "autoscaling",
                "resource_type": "launch_configuration",
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
                "resource_family": "autoscaling",
                "resource_type": "launch_template",
                "resource_id": lt_id,
                "resource_arn": f"arn:aws:ec2:{region}:*:launch-template/{lt_id}",
            }
        )
