"""
ELB Service Scanner
------------------

Scans ELBv2 resources: load balancers, target groups, listeners, and
listener rules — a dependent traversal (listeners hang off load
balancers, rules off listeners), annotated so the output processors can
name each resource's parent.
?Documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/elbv2.html
"""

from functools import partial
from typing import Any

from botocore.exceptions import ClientError

from aws_resource_inventory.lib.clients import get_scan_client
from aws_resource_inventory.lib.engine import (
    ResourceList,
    ScanResult,
    collect_pages,
    finish,
    map_parallel,
    run_parallel,
)
from aws_resource_inventory.lib.logging import get_logger
from aws_resource_inventory.lib.records import Resource

logger = get_logger()

# Per-parent listener/rule lookups fan out on threads.
ELB_CHILD_WORKERS = 4


def _attach_tags(elbv2_client: Any, arn_field: str, resource: dict[str, Any]) -> None:
    arn = resource[arn_field]
    try:
        descriptions = elbv2_client.describe_tags(ResourceArns=[arn]).get(
            "TagDescriptions", []
        )
        resource["Tags"] = descriptions[0].get("Tags", []) if descriptions else []
    except ClientError as e:
        logger.warning("Could not get tags for %s: %s", arn, e)
        resource["Tags"] = []


def _listeners_of(elbv2_client: Any, lb: dict[str, Any]) -> ResourceList:
    listeners = collect_pages(
        elbv2_client,
        "describe_listeners",
        "Listeners",
        LoadBalancerArn=lb["LoadBalancerArn"],
    )
    for listener in listeners:
        listener["LoadBalancerArn"] = lb["LoadBalancerArn"]
        listener["LoadBalancerName"] = lb["LoadBalancerName"]
    return listeners


def _rules_of(elbv2_client: Any, listener: dict[str, Any]) -> ResourceList:
    rules = collect_pages(
        elbv2_client, "describe_rules", "Rules", ListenerArn=listener["ListenerArn"]
    )
    for rule in rules:
        rule["ListenerArn"] = listener["ListenerArn"]
        rule["LoadBalancerArn"] = listener["LoadBalancerArn"]
        rule["LoadBalancerName"] = listener["LoadBalancerName"]
    return rules


def scan_elb(session: Any, region: str) -> ScanResult:
    """Scan all ELBv2 resources in the region (no tag filtering)."""
    elbv2_client = get_scan_client(session, "elbv2", region)

    def load_balancers_with_tags() -> ResourceList:
        load_balancers = collect_pages(
            elbv2_client, "describe_load_balancers", "LoadBalancers"
        )
        for lb in load_balancers:
            _attach_tags(elbv2_client, "LoadBalancerArn", lb)
        return load_balancers

    def target_groups_with_tags() -> ResourceList:
        target_groups = collect_pages(
            elbv2_client, "describe_target_groups", "TargetGroups"
        )
        for tg in target_groups:
            _attach_tags(elbv2_client, "TargetGroupArn", tg)
        return target_groups

    result = run_parallel(
        {
            "load_balancers": load_balancers_with_tags,
            "target_groups": target_groups_with_tags,
        },
        service="elb",
        region=region,
        max_workers=2,
    )

    # Dependent traversal: listeners per load balancer, rules per listener.
    # A failing parent is skipped with a warning; the rest keep going.
    listener_groups = map_parallel(
        partial(_listeners_of, elbv2_client),
        result["load_balancers"],
        max_workers=ELB_CHILD_WORKERS,
    )
    result["listeners"] = [listener for group in listener_groups for listener in group]

    rule_groups = map_parallel(
        partial(_rules_of, elbv2_client),
        result["listeners"],
        max_workers=ELB_CHILD_WORKERS,
    )
    result["listener_rules"] = [rule for group in rule_groups for rule in group]

    return finish("elb", region, result)


def process_elb_output(
    service_data: dict[str, Any], region: str, flattened_resources: list[Resource]
) -> None:
    """Process ELB scan results for output formatting."""
    # Load Balancers
    for lb in service_data.get("load_balancers", []):
        lb_name = lb.get("LoadBalancerName", "N/A")
        lb_arn = lb.get("LoadBalancerArn", "N/A")
        lb_type = lb.get("Type", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=lb_name,
                resource_type=f"elbv2:load_balancer_{lb_type}",
                resource_id="N/A",  # AWS api does not return id
                resource_arn=lb_arn,
            )
        )

    # Listeners
    for listener in service_data.get("listeners", []):
        listener_arn = listener.get("ListenerArn", "N/A")
        protocol = listener.get("Protocol", "N/A")
        port = listener.get("Port", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=f"{protocol}:{port}",
                resource_type="elbv2:listener",
                resource_id="N/A",  # AWS api does not return id
                resource_arn=listener_arn,
            )
        )

    # Listener Rules
    for rule in service_data.get("listener_rules", []):
        rule_arn = rule.get("RuleArn", "N/A")
        priority = rule.get("Priority", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=f"Rule-{priority}",
                resource_type="elbv2:listener_rule",
                resource_id="N/A",  # AWS api does not return id
                resource_arn=rule_arn,
            )
        )

    # Target Groups
    for tg in service_data.get("target_groups", []):
        tg_name = tg.get("TargetGroupName", "N/A")
        tg_arn = tg.get("TargetGroupArn", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=tg_name,
                resource_type="elbv2:target_group",
                resource_id="N/A",  # AWS api does not return id
                resource_arn=tg_arn,
            )
        )
