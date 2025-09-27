"""
ECS Service Scanner
------------------

Handles comprehensive scanning of ECS resources including
clusters, services, task definitions, and capacity providers.
Tag-based filtering is handled centrally by the Resource Groups Tagging API.
? Documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html

"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from botocore.exceptions import BotoCoreError, ClientError

from aws_scanner_lib.logging import get_logger, get_output_console

# Service logger
logger = get_logger("ecs_service")

# Separate console for user output to avoid interfering with logs and progress bars
output_console = get_output_console()

ECS_BATCH_SIZE = 10  # ECS describe_services supports up to 10 services per call
ECS_TASK_DEF_MAX_WORKERS = (
    4  # Parallel workers for task definition processing (reduced to avoid throttling)
)
# Only fetch latest 2 versions per task definition family (current + previous for rollback)


def _process_task_definition_parallel(ecs_client: Any, task_def_arn: str) -> Any:
    """Process a single task definition in parallel - describe and get tags."""
    try:
        task_def_details = ecs_client.describe_task_definition(
            taskDefinition=task_def_arn
        )
        task_def = task_def_details.get("taskDefinition")

        if not task_def:
            return None

        full_task_def_arn = task_def["taskDefinitionArn"]
        try:
            tags_response = ecs_client.list_tags_for_resource(
                resourceArn=full_task_def_arn
            )
            tags = tags_response.get("tags", [])
        except ClientError as e:
            output_console.print(
                f"[yellow]Could not get tags for task definition {full_task_def_arn}: {e}[/yellow]"
            )
            tags = []

        task_def["tags"] = tags
        return task_def

    except ClientError as e:
        output_console.print(
            f"[yellow]Could not describe task definition {task_def_arn}: {e}[/yellow]"
        )
        return None


def scan_ecs(
    session: Any,
    region: str,
) -> Dict[str, Any]:
    """Scan ECS resources in the specified region comprehensively."""
    logger.debug("Starting ECS service scan in region %s", region)

    # Show progress to user on separate console (will not conflict with logging or progress bars)
    if logger.is_debug_enabled():
        output_console.print(f"[blue]Scanning ECS resources in {region}[/blue]")

    logger.log_aws_operation(
        "ecs", "describe_clusters", region, parallel_workers=ECS_TASK_DEF_MAX_WORKERS
    )

    ecs_client = session.client("ecs", region_name=region)
    result = {}

    try:
        # Get all clusters comprehensively
        clusters = []
        paginator = ecs_client.get_paginator("list_clusters")
        page_iterator = paginator.paginate()

        for page in page_iterator:
            cluster_arns = page.get("clusterArns", [])
            if cluster_arns:
                cluster_details = ecs_client.describe_clusters(clusters=cluster_arns)
                clusters.extend(cluster_details.get("clusters", []))

        # Add tags to cluster objects for display purposes
        for cluster in clusters:
            cluster_arn = cluster["clusterArn"]
            try:
                tags_response = ecs_client.list_tags_for_resource(
                    resourceArn=cluster_arn
                )
                cluster["tags"] = tags_response.get("tags", [])
            except ClientError:
                cluster["tags"] = []

        # ECS Services - get all services from all clusters
        services = []
        for cluster in clusters:
            cluster_name = cluster["clusterName"]
            try:
                # List services with pagination
                service_arns = []
                paginator = ecs_client.get_paginator("list_services")
                page_iterator = paginator.paginate(cluster=cluster_name)

                for page in page_iterator:
                    service_arns.extend(page.get("serviceArns", []))

                # Process services in batches for efficiency
                for i in range(0, len(service_arns), ECS_BATCH_SIZE):
                    batch_arns = service_arns[i : i + ECS_BATCH_SIZE]

                    try:
                        service_details = ecs_client.describe_services(
                            cluster=cluster_name, services=batch_arns
                        )

                        for service in service_details.get("services", []):
                            service["clusterName"] = cluster_name
                            services.append(service)

                    except ClientError as e:
                        output_console.print(
                            f"[yellow]Could not describe services in cluster {cluster_name}: {e}[/yellow]"
                        )

            except ClientError as e:
                output_console.print(
                    f"[yellow]Could not list services in cluster {cluster_name}: {e}[/yellow]"
                )

        # Add tags to services for display purposes
        for service in services:
            service_arn = service.get("serviceArn", service.get("ResourceARN", ""))
            if service_arn:
                try:
                    tags_response = ecs_client.list_tags_for_resource(
                        resourceArn=service_arn
                    )
                    service["tags"] = tags_response.get("tags", [])
                except ClientError:
                    service["tags"] = []

                # Add cluster name if not already present
                if "clusterName" not in service and service_arn:
                    # Extract cluster from service ARN
                    arn_parts = service_arn.split("/")
                    if len(arn_parts) >= 2:
                        service["clusterName"] = arn_parts[-2]

        # Task Definitions - get only the latest 2 versions of each family
        task_definitions = []
        task_def_arns = []
        try:
            # Get all task definition families first
            families = []
            paginator = ecs_client.get_paginator("list_task_definition_families")
            page_iterator = paginator.paginate()

            for page in page_iterator:
                families.extend(page.get("families", []))

            # For each family, get only the latest 2 versions (current + previous for rollback)
            for family in families:
                try:
                    # List task definitions for this family, sorted by revision (newest first)
                    family_paginator = ecs_client.get_paginator("list_task_definitions")
                    family_iterator = family_paginator.paginate(
                        familyPrefix=family,
                        status="ACTIVE",
                        sort="DESC",  # Newest first
                    )

                    family_arns = []
                    for page in family_iterator:
                        family_arns.extend(page.get("taskDefinitionArns", []))

                    # Take only the first 2 (latest 2 versions)
                    latest_two = family_arns[:2]
                    task_def_arns.extend(latest_two)

                except (ClientError, BotoCoreError) as e:
                    output_console.print(
                        f"[yellow]Could not list task definitions for family {family}: {e}[/yellow]"
                    )

        except (ClientError, BotoCoreError) as e:
            output_console.print(
                f"[yellow]Could not list task definition families: {e}[/yellow]"
            )

        # Process task definitions in parallel for much better performance
        if task_def_arns:
            with ThreadPoolExecutor(max_workers=ECS_TASK_DEF_MAX_WORKERS) as executor:
                # Submit all task definition processing tasks
                future_to_arn = {
                    executor.submit(
                        _process_task_definition_parallel,
                        ecs_client,
                        task_def_arn,
                    ): task_def_arn
                    for task_def_arn in task_def_arns
                }

                # Collect results as they complete
                for future in as_completed(future_to_arn):
                    try:
                        result_task_def = future.result()
                        if result_task_def is not None:
                            task_definitions.append(result_task_def)
                    except (ClientError, BotoCoreError) as e:
                        task_def_arn = future_to_arn[future]
                        output_console.print(
                            f"[yellow]Error processing task definition {task_def_arn}: {e}[/yellow]"
                        )

        # Capacity Providers (if any clusters exist)
        capacity_providers = []
        if clusters:
            try:
                # Note: describe_capacity_providers doesn't support pagination
                # We'll use the direct API call instead
                response = ecs_client.describe_capacity_providers()
                capacity_providers = response.get("capacityProviders", [])

            except (ClientError, BotoCoreError) as e:
                output_console.print(
                    f"[yellow]Could not list capacity providers: {e}[/yellow]"
                )

        result["clusters"] = clusters
        result["services"] = services
        result["task_definitions"] = task_definitions
        result["capacity_providers"] = capacity_providers

    except BotoCoreError as e:
        logger.error("ECS scan failed in region %s: %s", region, str(e))
        logger.log_error_context(e, {"region": region, "operation": "ecs_scan"})

    # Log completion with resource count
    total_resources = sum(len(result.get(key, [])) for key in result.keys())
    logger.info(
        "ECS scan completed in region %s: %d total resources", region, total_resources
    )

    # Debug-level details about each resource type
    for resource_type, resources in result.items():
        if resources:
            logger.debug(
                "ECS %s in %s: %d resources", resource_type, region, len(resources)
            )

    return result


def process_ecs_output(
    service_data: Dict[str, Any], region: str, flattened_resources: List[Dict[str, Any]]
) -> None:
    """Process ECS scan results for output formatting."""
    # ECS Clusters
    for cluster in service_data.get("clusters", []):
        cluster_name = cluster.get("clusterName", "N/A")
        cluster_arn = cluster.get("clusterArn", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_type": "ecs:cluster",
                "resource_id": cluster_name,
                "resource_arn": cluster_arn,
            }
        )

    # ECS Services
    for service in service_data.get("services", []):
        service_name = service.get("serviceName", "N/A")
        service_arn = service.get("serviceArn", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_type": "ecs:service",
                "resource_id": service_name,
                "resource_arn": service_arn,
            }
        )

    # ECS Task Definitions
    for task_def in service_data.get("task_definitions", []):
        task_def_arn = task_def.get("taskDefinitionArn", "N/A")
        task_def_name = task_def_arn.split("/")[-1] if task_def_arn != "N/A" else "N/A"

        flattened_resources.append(
            {
                "region": region,
                "resource_type": "ecs:task_definition",  # Unified format: service:type
                "resource_id": task_def_name,
                "resource_arn": task_def_arn,
            }
        )

    # ECS Capacity Providers
    for cp in service_data.get("capacity_providers", []):
        cp_name = cp.get("name", "N/A")
        cp_arn = cp.get("capacityProviderArn", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_type": "ecs:capacity_provider",  # Unified format: service:type
                "resource_id": cp_name,
                "resource_arn": cp_arn,
            }
        )
