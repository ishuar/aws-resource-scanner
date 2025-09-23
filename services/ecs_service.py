"""
ECS Service Scanner
------------------

Handles scanning of ECS resources including clusters, services, task definitions, and capacity providers.
"""

import botocore
from rich.console import Console

console = Console()


def scan_ecs(session, region, tag_key=None, tag_value=None):
    """Scan ECS resources in the specified region with optimized API filtering and pagination."""
    ecs_client = session.client("ecs", region_name=region)
    result = {}
    try:
        # ECS Clusters with pagination
        clusters = []
        paginator = ecs_client.get_paginator("list_clusters")
        page_iterator = paginator.paginate()

        for page in page_iterator:
            cluster_arns = page.get("clusterArns", [])

            # Get cluster details in batches for efficiency
            if cluster_arns:
                cluster_details = ecs_client.describe_clusters(clusters=cluster_arns)
                clusters.extend(cluster_details.get("clusters", []))

        # Filter clusters by tags
        filtered_clusters = []
        for cluster in clusters:
            cluster_arn = cluster["clusterArn"]
            try:
                tags_response = ecs_client.list_tags_for_resource(
                    resourceArn=cluster_arn
                )
                tags = tags_response.get("tags", [])

                if tag_key and tag_value:
                    if any(
                        t["key"] == tag_key and t["value"] == tag_value for t in tags
                    ):
                        cluster["tags"] = tags
                        filtered_clusters.append(cluster)
                else:
                    cluster["tags"] = tags
                    filtered_clusters.append(cluster)

            except botocore.exceptions.ClientError as e:
                console.print(
                    f"[yellow]Could not get tags for cluster {cluster_arn}: {e}[/yellow]"
                )

        # ECS Services with pagination
        filtered_services = []
        for cluster in filtered_clusters:
            cluster_name = cluster["clusterName"]
            try:
                # List services with pagination
                service_arns = []
                paginator = ecs_client.get_paginator("list_services")
                page_iterator = paginator.paginate(cluster=cluster_name)

                for page in page_iterator:
                    service_arns.extend(page.get("serviceArns", []))

                # Process services in batches for efficiency
                batch_size = (
                    10  # ECS describe_services supports up to 10 services per call
                )
                for i in range(0, len(service_arns), batch_size):
                    batch_arns = service_arns[i : i + batch_size]

                    try:
                        service_details = ecs_client.describe_services(
                            cluster=cluster_name, services=batch_arns
                        )

                        for service in service_details.get("services", []):
                            service_arn = service["serviceArn"]
                            try:
                                tags_response = ecs_client.list_tags_for_resource(
                                    resourceArn=service_arn
                                )
                                tags = tags_response.get("tags", [])

                                if tag_key and tag_value:
                                    if any(
                                        t["key"] == tag_key and t["value"] == tag_value
                                        for t in tags
                                    ):
                                        service["tags"] = tags
                                        service["clusterName"] = cluster_name
                                        filtered_services.append(service)
                                else:
                                    service["tags"] = tags
                                    service["clusterName"] = cluster_name
                                    filtered_services.append(service)

                            except botocore.exceptions.ClientError as e:
                                console.print(
                                    f"[yellow]Could not get tags for service {service_arn}: {e}[/yellow]"
                                )

                    except botocore.exceptions.ClientError as e:
                        console.print(
                            f"[yellow]Could not describe services in cluster {cluster_name}: {e}[/yellow]"
                        )

            except botocore.exceptions.ClientError as e:
                console.print(
                    f"[yellow]Could not list services in cluster {cluster_name}: {e}[/yellow]"
                )

        # Task Definitions with pagination
        task_definitions = []
        try:
            paginator = ecs_client.get_paginator("list_task_definitions")
            page_iterator = paginator.paginate()

            for page in page_iterator:
                task_def_arns = page.get("taskDefinitionArns", [])

                # Process task definitions in batches
                batch_size = 10
                for i in range(0, len(task_def_arns), batch_size):
                    batch_arns = task_def_arns[i : i + batch_size]

                    try:
                        task_def_details = ecs_client.describe_task_definition(
                            taskDefinition=batch_arns[
                                0
                            ]  # Process one at a time for describe_task_definition
                        )

                        task_def = task_def_details.get("taskDefinition")
                        if task_def:
                            task_def_arn = task_def["taskDefinitionArn"]
                            try:
                                tags_response = ecs_client.list_tags_for_resource(
                                    resourceArn=task_def_arn
                                )
                                tags = tags_response.get("tags", [])

                                if tag_key and tag_value:
                                    if any(
                                        t["key"] == tag_key and t["value"] == tag_value
                                        for t in tags
                                    ):
                                        task_def["tags"] = tags
                                        task_definitions.append(task_def)
                                else:
                                    task_def["tags"] = tags
                                    task_definitions.append(task_def)

                            except botocore.exceptions.ClientError as e:
                                console.print(
                                    f"[yellow]Could not get tags for task definition {task_def_arn}: {e}[/yellow]"
                                )

                    except botocore.exceptions.ClientError as e:
                        console.print(
                            f"[yellow]Could not describe task definition: {e}[/yellow]"
                        )

        except Exception as e:
            console.print(f"[yellow]Could not list task definitions: {e}[/yellow]")

        # Capacity Providers (if any clusters exist)
        capacity_providers = []
        if filtered_clusters:
            try:
                # Note: describe_capacity_providers doesn't support pagination
                # We'll use the direct API call instead
                response = ecs_client.describe_capacity_providers()
                capacity_providers = response.get("capacityProviders", [])

            except Exception as e:
                console.print(
                    f"[yellow]Could not list capacity providers: {e}[/yellow]"
                )

        result["clusters"] = filtered_clusters
        result["services"] = filtered_services
        result["task_definitions"] = task_definitions
        result["capacity_providers"] = capacity_providers

    except botocore.exceptions.BotoCoreError as e:
        console.print(f"[red]ECS scan failed: {e}[/red]")
    return result


def process_ecs_output(service_data, region, flattened_resources):
    """Process ECS scan results for output formatting."""
    # ECS Clusters
    for cluster in service_data.get("clusters", []):
        cluster_name = cluster.get("clusterName", "N/A")
        cluster_arn = cluster.get("clusterArn", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": cluster_name,
                "resource_family": "ecs",
                "resource_type": "cluster",
                "resource_id": (
                    cluster_arn.split("/")[-1] if cluster_arn != "N/A" else "N/A"
                ),
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
                "resource_name": service_name,
                "resource_family": "ecs",
                "resource_type": "service",
                "resource_id": (
                    service_arn.split("/")[-1] if service_arn != "N/A" else "N/A"
                ),
                "resource_arn": service_arn,
            }
        )

    # ECS Task Definitions
    for task_def in service_data.get("task_definitions", []):
        task_def_family = task_def.get("family", "N/A")
        task_def_arn = task_def.get("taskDefinitionArn", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": f"{task_def_family}:{task_def.get('revision', 'N/A')}",
                "resource_family": "ecs",
                "resource_type": "task_definition",
                "resource_id": (
                    task_def_arn.split("/")[-1] if task_def_arn != "N/A" else "N/A"
                ),
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
                "resource_name": cp_name,
                "resource_family": "ecs",
                "resource_type": "capacity_provider",
                "resource_id": cp_name,
                "resource_arn": cp_arn,
            }
        )
