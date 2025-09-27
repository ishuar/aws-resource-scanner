"""
ELB Service Scanner
------------------

Handles scanning of ELB resources including load balancers, listeners, rules, and target groups.
?Documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/elbv2.html

"""

from typing import Any, Dict, List

from botocore.exceptions import BotoCoreError, ClientError

from aws_scanner_lib.logging import get_logger, get_output_console

# Service logger
logger = get_logger("elb_service")

# Separate console for user output to avoid interfering with logs and progress bars
output_console = get_output_console()


def scan_elb(
    session: Any,
    region: str,
) -> Dict[str, Any]:
    """Scan all ELB resources in the specified region without tag filtering."""
    logger.debug("Starting ELB service scan in region %s", region)

    # Show progress to user on separate console (will not conflict with logging or progress bars)
    if logger.is_debug_enabled():
        output_console.print(f"[blue]Scanning ELB resources in {region}[/blue]")

    logger.log_aws_operation("elbv2", "describe_load_balancers", region)

    elbv2_client = session.client("elbv2", region_name=region)
    result = {}
    try:
        # Load Balancers (ALB/NLB) with pagination
        load_balancers = []
        paginator = elbv2_client.get_paginator("describe_load_balancers")
        page_iterator = paginator.paginate()

        for page in page_iterator:
            load_balancers.extend(page["LoadBalancers"])

        # Get all load balancers with their tags (no filtering)
        for lb in load_balancers:
            lb_arn = lb["LoadBalancerArn"]
            try:
                tags_response = elbv2_client.describe_tags(ResourceArns=[lb_arn])
                tag_descriptions = tags_response.get("TagDescriptions", [])
                lb["Tags"] = (
                    tag_descriptions[0].get("Tags", []) if tag_descriptions else []
                )
            except ClientError as e:
                console.print(
                    f"[yellow]Could not get tags for load balancer {lb_arn}: {e}[/yellow]"
                )
                lb["Tags"] = []

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

        # Get all target groups with their tags (no filtering)
        for tg in target_groups:
            tg_arn = tg["TargetGroupArn"]
            try:
                tags_response = elbv2_client.describe_tags(ResourceArns=[tg_arn])
                tag_descriptions = tags_response.get("TagDescriptions", [])
                tg["Tags"] = (
                    tag_descriptions[0].get("Tags", []) if tag_descriptions else []
                )
            except ClientError as e:
                console.print(
                    f"[yellow]Could not get tags for target group {tg_arn}: {e}[/yellow]"
                )
                tg["Tags"] = []

        # Listeners (get listeners for all load balancers)
        listeners = []
        for lb in load_balancers:
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
                except ClientError as e:
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
                except ClientError as e:
                    console.print(
                        f"[yellow]Could not get rules for {listener['ListenerArn']}: {e}[/yellow]"
                    )

        result["load_balancers"] = load_balancers
        result["target_groups"] = target_groups
        result["listeners"] = listeners
        result["rules"] = rules

        # Listeners
        filtered_listeners = []
        for lb in load_balancers:
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
            except ClientError as e:
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
            except ClientError as e:
                console.print(
                    f"[yellow]Could not get rules for listener {listener_arn}: {e}[/yellow]"
                )

        result["listener_rules"] = filtered_rules

    except BotoCoreError as e:
        logger.error("ELB scan failed in region %s: %s", region, str(e))
        logger.log_error_context(e, {"region": region, "operation": "elb_scan"})

    # Log completion with resource count
    total_resources = sum(len(result.get(key, [])) for key in result.keys())
    logger.info("ELB scan completed in region %s: %d total resources", region, total_resources)

    # Debug-level details about each resource type
    for resource_type, resources in result.items():
        if resources:
            logger.debug("ELB %s in %s: %d resources", resource_type, region, len(resources))

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
                "resource_type": f"elbv2:load_balancer_{lb_type}",
                "resource_id": "N/A",  # AWS api does not return id
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
                "resource_type": "elbv2:listener",
                "resource_id": "N/A",  # AWS api does not return id
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
                "resource_type": "elbv2:listener_rule",
                "resource_id": "N/A",  # AWS api does not return id
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
                "resource_type": "elbv2:target_group",
                "resource_id": "N/A",  # AWS api does not return id
                "resource_arn": tg_arn,
            }
        )
