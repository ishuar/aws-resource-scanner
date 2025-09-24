"""
Auto Scaling Service Scanner
---------------------------

Handles scanning of Auto Scaling resources including auto scaling groups,
launch configurations, and launch templates.
"""

from typing import Any, Dict, List, Optional

import botocore
from rich.console import Console

console = Console()


def scan_autoscaling(
    session: Any,
    region: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> Dict[str, Any]:
    """Scan Auto Scaling resources in the specified region."""
    autoscaling_client = session.client("autoscaling", region_name=region)
    result = {}
    try:
        # Auto Scaling Groups
        asg_response = autoscaling_client.describe_auto_scaling_groups()
        asgs = asg_response.get("AutoScalingGroups", [])

        filtered_asgs = []
        for asg in asgs:
            if tag_key and tag_value:
                # Check if ASG has the required tag
                if any(
                    t["Key"] == tag_key and t["Value"] == tag_value
                    for t in asg.get("Tags", [])
                ):
                    filtered_asgs.append(asg)
            else:
                filtered_asgs.append(asg)

        result["auto_scaling_groups"] = filtered_asgs

        # Launch Configurations
        lc_response = autoscaling_client.describe_launch_configurations()
        launch_configs = lc_response.get("LaunchConfigurations", [])

        # Note: Launch configurations don't support tags, so we filter by ASG usage
        filtered_launch_configs = []
        if not tag_key and not tag_value:
            # Include all if no filtering
            filtered_launch_configs = launch_configs
        else:
            # Only include launch configs used by filtered ASGs
            used_lc_names = {
                asg.get("LaunchConfigurationName")
                for asg in filtered_asgs
                if asg.get("LaunchConfigurationName")
            }
            filtered_launch_configs = [
                lc
                for lc in launch_configs
                if lc.get("LaunchConfigurationName") in used_lc_names
            ]

        result["launch_configurations"] = filtered_launch_configs

        # Launch Templates (newer alternative to launch configurations)
        try:
            ec2_client = session.client("ec2", region_name=region)
            lt_response = ec2_client.describe_launch_templates()
            launch_templates = lt_response.get("LaunchTemplates", [])

            def filter_tags_ec2(
                resources: List[Dict[str, Any]],
            ) -> List[Dict[str, Any]]:
                if tag_key and tag_value:
                    return [
                        r
                        for r in resources
                        if any(
                            t["Key"] == tag_key and t["Value"] == tag_value
                            for t in r.get("Tags", [])
                        )
                    ]
                return resources

            filtered_launch_templates = filter_tags_ec2(launch_templates)
            result["launch_templates"] = filtered_launch_templates

        except botocore.exceptions.ClientError as e:
            console.print(f"[yellow]Could not get launch templates: {e}[/yellow]")
            result["launch_templates"] = []

    except botocore.exceptions.BotoCoreError as e:
        console.print(f"[red]Auto Scaling scan failed: {e}[/red]")
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
