"""
Outputs module for AWS Scanner

Handles formatting and output of scan results in various formats (JSON, table, markdown).
"""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table

from services import (
    process_autoscaling_output,
    process_ec2_output,
    process_ecs_output,
    process_elb_output,
    process_s3_output,
    process_vpc_output,
)

console = Console()
# Minimum width for tables to ensure readability
TABLE_MINIMUM_WIDTH = 86


def create_aws_resources_table(flattened_resources: List[Dict[str, Any]]) -> Table:
    """
    Create a standardized AWS resources table with consistent formatting.

    Args:
        flattened_resources: List of resource dictionaries with standardized format

    Returns:
        Table: Rich Table object ready for display
    """
    table = Table(
        title="AWS Resources", min_width=TABLE_MINIMUM_WIDTH, border_style="bright_blue"
    )
    table.add_column("Region", style="blue")
    table.add_column("Resource Type", style="yellow")
    table.add_column("Resource ID", style="green")
    table.add_column("Resource ARN", style="white")

    for resource in flattened_resources:
        table.add_row(
            resource.get("region", "N/A"),
            # Use unified resource_type format (service:type)
            resource.get("resource_type", "N/A"),
            resource.get("resource_id", "N/A"),
            resource.get("resource_arn", "N/A"),
        )

    return table


def ensure_output_directory(output_file: Path) -> None:
    """Ensure the output directory exists, create if it doesn't."""
    output_dir = output_file.parent
    if not output_dir.exists():
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            console.print(f"[dim]Created output directory: {output_dir}[/dim]")
        except Exception as e:
            console.print(
                f"[red]Failed to create output directory {output_dir}: {e}[/red]"
            )
            raise


def generate_markdown_summary(
    flattened_resources: List[Dict[str, Any]], results: Dict[str, Any]
) -> str:
    """Generate a markdown summary report from scan results."""
    md_content = []

    # Header
    md_content.append("# AWS Resources Scan Report")
    md_content.append(
        f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    md_content.append(f"**Total Resources:** {len(flattened_resources)}")

    # Summary by region
    md_content.append("\n## Summary by Region")
    region_counts = Counter(r["region"] for r in flattened_resources)
    for region, count in sorted(region_counts.items()):
        md_content.append(f"- **{region}**: {count} resources")

    # Summary by service (extracted from resource_type)
    md_content.append("\n## Summary by Service")
    service_counts = Counter(
        (
            r["resource_type"].split(":")[0]
            if ":" in r["resource_type"]
            else r["resource_type"]
        )
        for r in flattened_resources
    )
    for service, count in sorted(service_counts.items()):
        md_content.append(f"- **{service.upper()}**: {count} resources")

    # Summary by resource type
    md_content.append("\n## Summary by Resource Type")
    type_counts = Counter(r["resource_type"] for r in flattened_resources)
    for resource_type, count in sorted(type_counts.items()):
        md_content.append(f"- **{resource_type}**: {count}")

    # Detailed breakdown by region and service
    md_content.append("\n## Detailed Resources")

    for region in sorted(region_counts.keys()):
        region_resources = [r for r in flattened_resources if r["region"] == region]
        if not region_resources:
            continue

        md_content.append(f"\n### {region}")

        # Group by service within region (extracted from resource_type)
        region_services: Dict[str, List[Dict[str, Any]]] = {}
        for resource in region_resources:
            service = (
                resource["resource_type"].split(":")[0]
                if ":" in resource["resource_type"]
                else resource["resource_type"]
            )
            if service not in region_services:
                region_services[service] = []
            region_services[service].append(resource)

        for service in sorted(region_services.keys()):
            service_resources = region_services[service]
            md_content.append(
                f"\n#### {service.upper()} ({len(service_resources)} resources)"
            )

            md_content.append("| Resource Name | Type | ID | ARN |")
            md_content.append("|---------------|------|----|----|")

            for resource in sorted(
                service_resources,
                key=lambda x: x.get("resource_name", x["resource_id"]),
            ):
                name = resource.get("resource_name", resource["resource_id"]).replace(
                    "|", "\\|"
                )  # Escape pipes
                resource_type = resource["resource_type"].replace("|", "\\|")
                resource_id = resource["resource_id"].replace("|", "\\|")
                arn = resource["resource_arn"].replace("|", "\\|")

                # Format ID and ARN with code blocks for better readability
                formatted_id = f"`{resource_id}`" if resource_id != "N/A" else "N/A"
                formatted_arn = f"`{arn}`" if arn != "N/A" else "N/A"

                md_content.append(
                    f"| {name} | {resource_type} | {formatted_id} | {formatted_arn} |"
                )

    # Add scan metadata
    md_content.append("\n## Scan Metadata")
    md_content.append("- **Tool**: AWS Service Scanner")
    md_content.append("- **Version**: Modular Version with Advanced Optimizations")

    return "\n".join(md_content)


def process_generic_service_output(
    service_data: Dict[str, Any],
    region: str,
    flattened_resources: List[Dict[str, Any]],
) -> None:
    """
    Generic processor for cross-service resources discovered via Resource Groups API.

    This handles any AWS service that doesn't have a specific processor, ensuring
    all discovered resources are included in the unified output format.
    """
    for resource_type_key, resources in service_data.items():
        if isinstance(resources, list):
            for resource in resources:
                if isinstance(resource, dict):
                    # Extract resource details from Resource Groups API format
                    resource_arn = resource.get("ResourceARN", "")
                    resource_id = resource.get("ResourceId", "")
                    resource_type = resource.get("ResourceType", resource_type_key)

                    # Create standardized resource entry with unified format
                    flattened_resource = {
                        "region": region,
                        "resource_type": resource_type,  # Already in service:type format from Resource Groups API
                        "resource_id": resource_id or "N/A",
                        "resource_arn": resource_arn or "N/A",
                    }

                    flattened_resources.append(flattened_resource)


def _is_resource_groups_api_data(service_data: Dict[str, Any]) -> bool:
    """
    Detect if service_data comes from Resource Groups API vs traditional service APIs.

    Resource Groups API data has a different structure with ResourceARN, ResourceId, ResourceType keys.
    Traditional API data has service-specific resource object structures.
    """
    if not isinstance(service_data, dict):
        return False  # type: ignore[unreachable]

    rg_signature_keys = {"ResourceARN", "ResourceId", "ResourceType"}

    for resource_list in service_data.values():
        # Skip non-list or empty values
        if not isinstance(resource_list, list) or not resource_list:
            continue

        # Skip non-dict resources
        sample_resource = resource_list[0]
        if not isinstance(sample_resource, dict):
            continue

        # Check if this matches Resource Groups API format
        sample_keys = set(sample_resource.keys())
        if rg_signature_keys.issubset(sample_keys):
            return True

    return False


def output_results(
    results: Dict[str, Any], output_file: Path, output_format: str
) -> int:
    """Process results using modular output processors and format for output.

    Returns:
        int: The total number of flattened resources found.
    """

    # Flatten results into a list of resources with the required columns
    flattened_resources: List[Dict[str, Any]] = []

    for region, services in results.items():
        for service_name, service_data in services.items():
            if not service_data:  # Skip empty services
                continue

            # Detect if this is Resource Groups API data vs traditional API data
            is_resource_groups_data = _is_resource_groups_api_data(service_data)

            # Route to appropriate processor based on data source
            if is_resource_groups_data:
                # All Resource Groups API data goes through generic processor
                process_generic_service_output(
                    service_data, region, flattened_resources
                )
            else:
                # Traditional API data goes through service-specific processors
                if service_name == "ec2":
                    process_ec2_output(service_data, region, flattened_resources)
                elif service_name == "s3":
                    process_s3_output(service_data, region, flattened_resources)
                elif service_name == "ecs":
                    process_ecs_output(service_data, region, flattened_resources)
                elif service_name == "elb":
                    process_elb_output(service_data, region, flattened_resources)
                elif service_name == "vpc":
                    process_vpc_output(service_data, region, flattened_resources)
                elif service_name == "autoscaling":
                    process_autoscaling_output(
                        service_data, region, flattened_resources
                    )
                else:
                    # Fallback to generic processor for unknown traditional services
                    process_generic_service_output(
                        service_data, region, flattened_resources
                    )

    # Ensure output directory exists before writing files
    ensure_output_directory(output_file)

    # Output in the requested format
    if output_format == "json":
        output_file.write_text(json.dumps(flattened_resources, indent=2))
        console.print(f"[green]Results saved to {output_file}[/green]")
        # Also print to console for immediate viewing
        console.print(json.dumps(flattened_resources, indent=2))
    elif output_format == "table":
        # Create and display the standardized table
        table = create_aws_resources_table(flattened_resources)
        console.print(table)

        # Also save table data as JSON to file
        output_file.write_text(json.dumps(flattened_resources, indent=2))
        console.print(f"[green]Data also saved to {output_file}[/green]")
    elif output_format in ("md", "markdown"):
        # Generate markdown summary report
        markdown_content = generate_markdown_summary(flattened_resources, results)

        # Change extension to .md for markdown files
        md_output_file = output_file.with_suffix(".md")
        # Ensure directory exists for markdown file (might have different path)
        ensure_output_directory(md_output_file)
        md_output_file.write_text(markdown_content)
        console.print(f"[green]Markdown report saved to {md_output_file}[/green]")

        # Display the table view in terminal as well
        console.print("\n[bold blue]Resource Table View:[/bold blue]")
        table = create_aws_resources_table(flattened_resources)
        console.print(table)

        # Also display a summary in console
        console.print("\n[bold blue]Markdown Summary Generated:[/bold blue]")
        console.print(f"Total resources: {len(flattened_resources)}")

        # Count by service (extracted from resource_type)
        service_counts = Counter(
            (
                r["resource_type"].split(":")[0]
                if ":" in r["resource_type"]
                else r["resource_type"]
            )
            for r in flattened_resources
        )
        for service, count in service_counts.items():
            console.print(f"  {service}: {count} resources")

    else:
        console.print(
            f"[red]Unknown output format '{output_format}'. Supported: json, table, md or markdown[/red]"
        )

    return len(flattened_resources)


def compare_with_existing(output_file: Path, new_data: Dict[str, Any]) -> None:
    """Compare new scan results with existing file to detect changes."""
    if output_file.exists():
        # Import DeepDiff only when needed to avoid circular import issues
        from deepdiff import DeepDiff

        existing_data = json.loads(output_file.read_text())
        diff = DeepDiff(existing_data, new_data, ignore_order=True)
        if not diff:
            console.print("[green]No changes detected since last scan.[/green]")
        else:
            console.print("[yellow]Changes detected![/yellow]")
            console.print(json.dumps(diff, indent=2, default=str))
