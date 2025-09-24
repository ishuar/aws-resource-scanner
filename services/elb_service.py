"""
ELB Service Scanner
------------------

Handles scanning of ELB resources including load balancers, listeners, rules, and target groups.
"""

from typing import Any, Dict, List, Optional

import botocore
from rich.console import Console

console = Console()


def scan_elb(
    session: Any,
    region: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> Dict[str, Any]:
    """Scan ELB resources in the specified region with optimized API filtering and pagination."""
    elbv2_client = session.client("elbv2", region_name=region)
    result = {}
    try:
        # Load Balancers (ALB/NLB) with pagination
        load_balancers = []
        paginator = elbv2_client.get_paginator("describe_load_balancers")
        page_iterator = paginator.paginate()

        for page in page_iterator:
            load_balancers.extend(page["LoadBalancers"])

        # Filter load balancers by tags (ELB doesn't support server-side tag filtering)
        filtered_load_balancers = []
        for lb in load_balancers:
            lb_arn = lb["LoadBalancerArn"]
            try:
                tags_response = elbv2_client.describe_tags(ResourceArns=[lb_arn])
                tag_descriptions = tags_response.get("TagDescriptions", [])

                if tag_descriptions:
                    tags = tag_descriptions[0].get("Tags", [])

                    if tag_key and tag_value:
                        if any(
                            t["Key"] == tag_key and t["Value"] == tag_value
                            for t in tags
                        ):
                            lb["Tags"] = tags
                            filtered_load_balancers.append(lb)
                    else:
                        lb["Tags"] = tags
                        filtered_load_balancers.append(lb)
                elif not tag_key and not tag_value:
                    lb["Tags"] = []
                    filtered_load_balancers.append(lb)

            except botocore.exceptions.ClientError as e:
                console.print(
                    f"[yellow]Could not get tags for load balancer {lb_arn}: {e}[/yellow]"
                )

        # Target Groups with pagination
        target_groups = []
        try:
            paginator = elbv2_client.get_paginator("describe_target_groups")
            page_iterator = paginator.paginate()

            for page in page_iterator:
                target_groups.extend(page["TargetGroups"])
        except Exception:
            # Fallback to non-paginated call
            target_groups_response = elbv2_client.describe_target_groups()
            target_groups = target_groups_response.get("TargetGroups", [])

        # Filter target groups by tags
        filtered_target_groups = []
        for tg in target_groups:
            tg_arn = tg["TargetGroupArn"]
            try:
                tags_response = elbv2_client.describe_tags(ResourceArns=[tg_arn])
                tag_descriptions = tags_response.get("TagDescriptions", [])

                if tag_descriptions:
                    tags = tag_descriptions[0].get("Tags", [])

                    if tag_key and tag_value:
                        if any(
                            t["Key"] == tag_key and t["Value"] == tag_value
                            for t in tags
                        ):
                            tg["Tags"] = tags
                            filtered_target_groups.append(tg)
                    else:
                        tg["Tags"] = tags
                        filtered_target_groups.append(tg)
                elif not tag_key and not tag_value:
                    tg["Tags"] = []
                    filtered_target_groups.append(tg)

            except botocore.exceptions.ClientError as e:
                console.print(
                    f"[yellow]Could not get tags for target group {tg_arn}: {e}[/yellow]"
                )

        # Listeners (get listeners for filtered load balancers)
        listeners = []
        for lb in filtered_load_balancers:
            try:
                paginator = elbv2_client.get_paginator("describe_listeners")
                page_iterator = paginator.paginate(
                    LoadBalancerArn=lb["LoadBalancerArn"]
                )

                for page in page_iterator:
                    for listener in page["Listeners"]:
                        listener["LoadBalancerArn"] = lb["LoadBalancerArn"]
                        listeners.append(listener)
            except Exception:
                # Fallback to non-paginated call
                try:
                    listeners_response = elbv2_client.describe_listeners(
                        LoadBalancerArn=lb["LoadBalancerArn"]
                    )
                    for listener in listeners_response["Listeners"]:
                        listener["LoadBalancerArn"] = lb["LoadBalancerArn"]
                        listeners.append(listener)
                except botocore.exceptions.ClientError as e:
                    console.print(
                        f"[yellow]Could not get listeners for {lb['LoadBalancerArn']}: {e}[/yellow]"
                    )

        # Rules (get rules for listeners)
        rules = []
        for listener in listeners:
            try:
                paginator = elbv2_client.get_paginator("describe_rules")
                page_iterator = paginator.paginate(ListenerArn=listener["ListenerArn"])

                for page in page_iterator:
                    for rule in page["Rules"]:
                        rule["ListenerArn"] = listener["ListenerArn"]
                        rules.append(rule)
            except Exception:
                # Fallback to non-paginated call
                try:
                    rules_response = elbv2_client.describe_rules(
                        ListenerArn=listener["ListenerArn"]
                    )
                    for rule in rules_response["Rules"]:
                        rule["ListenerArn"] = listener["ListenerArn"]
                        rules.append(rule)
                except botocore.exceptions.ClientError as e:
                    console.print(
                        f"[yellow]Could not get rules for {listener['ListenerArn']}: {e}[/yellow]"
                    )

        result["load_balancers"] = filtered_load_balancers
        result["target_groups"] = filtered_target_groups
        result["listeners"] = listeners
        result["rules"] = rules

        # Listeners
        filtered_listeners = []
        for lb in filtered_load_balancers:
            lb_arn = lb["LoadBalancerArn"]
            try:
                listeners_response = elbv2_client.describe_listeners(
                    LoadBalancerArn=lb_arn
                )
                listeners = listeners_response.get("Listeners", [])

                for listener in listeners:
                    # Add reference to load balancer
                    listener["LoadBalancerArn"] = lb_arn
                    listener["LoadBalancerName"] = lb["LoadBalancerName"]
                    filtered_listeners.append(listener)
            except botocore.exceptions.ClientError as e:
                console.print(
                    f"[yellow]Could not get listeners for load balancer {lb_arn}: {e}[/yellow]"
                )

        result["listeners"] = filtered_listeners

        # Listener Rules
        filtered_rules = []
        for listener in filtered_listeners:
            listener_arn = listener["ListenerArn"]
            try:
                rules_response = elbv2_client.describe_rules(ListenerArn=listener_arn)
                rules = rules_response.get("Rules", [])

                for rule in rules:
                    # Add reference to listener
                    rule["ListenerArn"] = listener_arn
                    rule["LoadBalancerArn"] = listener["LoadBalancerArn"]
                    rule["LoadBalancerName"] = listener["LoadBalancerName"]
                    filtered_rules.append(rule)
            except botocore.exceptions.ClientError as e:
                console.print(
                    f"[yellow]Could not get rules for listener {listener_arn}: {e}[/yellow]"
                )

        result["listener_rules"] = filtered_rules

    except botocore.exceptions.BotoCoreError as e:
        console.print(f"[red]ELB scan failed: {e}[/red]")
    return result


def process_elb_output(
    service_data: Dict[str, Any], region: str, flattened_resources: List[Dict[str, Any]]
) -> None:
    """Process ELB scan results for output formatting."""
    # Load Balancers
    for lb in service_data.get("load_balancers", []):
        lb_name = lb.get("LoadBalancerName", "N/A")
        lb_arn = lb.get("LoadBalancerArn", "N/A")
        lb_type = lb.get("Type", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": lb_name,
                "resource_family": "elb",
                "resource_type": f"load_balancer_{lb_type}",
                "resource_id": lb_arn.split("/")[-1] if lb_arn != "N/A" else "N/A",
                "resource_arn": lb_arn,
            }
        )

    # Listeners
    for listener in service_data.get("listeners", []):
        listener_arn = listener.get("ListenerArn", "N/A")
        protocol = listener.get("Protocol", "N/A")
        port = listener.get("Port", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": f"{protocol}:{port}",
                "resource_family": "elb",
                "resource_type": "listener",
                "resource_id": (
                    listener_arn.split("/")[-1] if listener_arn != "N/A" else "N/A"
                ),
                "resource_arn": listener_arn,
            }
        )

    # Listener Rules
    for rule in service_data.get("listener_rules", []):
        rule_arn = rule.get("RuleArn", "N/A")
        priority = rule.get("Priority", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": f"Rule-{priority}",
                "resource_family": "elb",
                "resource_type": "listener_rule",
                "resource_id": rule_arn.split("/")[-1] if rule_arn != "N/A" else "N/A",
                "resource_arn": rule_arn,
            }
        )

    # Target Groups
    for tg in service_data.get("target_groups", []):
        tg_name = tg.get("TargetGroupName", "N/A")
        tg_arn = tg.get("TargetGroupArn", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": tg_name,
                "resource_family": "elb",
                "resource_type": "target_group",
                "resource_id": tg_arn.split("/")[-1] if tg_arn != "N/A" else "N/A",
                "resource_arn": tg_arn,
            }
        )
