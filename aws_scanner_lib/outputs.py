"""
Outputs module for AWS Scanner

Handles formatting and output of scan results in various formats (JSON, table, markdown).
"""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from deepdiff import DeepDiff
from rich.console import Console
from rich.table import Table

# Import service output processors
from services import (
    process_autoscaling_output,
    process_ec2_output,
    process_ecs_output,
    process_elb_output,
    process_s3_output,
    process_vpc_output,
)

console = Console()


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

    # Summary by service family
    md_content.append("\n## Summary by Service")
    service_counts = Counter(r["resource_family"] for r in flattened_resources)
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

        # Group by service within region
        region_services: Dict[str, List[Dict[str, Any]]] = {}
        for resource in region_resources:
            service = resource["resource_family"]
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

            for resource in sorted(service_resources, key=lambda x: x["resource_name"]):
                name = resource["resource_name"].replace("|", "\\|")  # Escape pipes
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

            # Process each service using modular processing functions
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
                process_autoscaling_output(service_data, region, flattened_resources)

    # Ensure output directory exists before writing files
    ensure_output_directory(output_file)

    # Output in the requested format
    if output_format == "json":
        output_file.write_text(json.dumps(flattened_resources, indent=2))
        console.print(f"[green]Results saved to {output_file}[/green]")
        # Also print to console for immediate viewing
        console.print(json.dumps(flattened_resources, indent=2))
    elif output_format == "table":
        table = Table(title="AWS Resources")
        table.add_column("Region", style="blue")
        table.add_column("Resource Name", style="cyan")
        table.add_column("Resource Family", style="magenta")
        table.add_column("Resource Type", style="yellow")
        table.add_column("Resource ID", style="green")
        table.add_column("Resource ARN", style="white")

        for resource in flattened_resources:
            table.add_row(
                resource.get("region", "N/A"),
                resource["resource_name"],
                resource["resource_family"],
                resource["resource_type"],
                resource["resource_id"],
                resource["resource_arn"],
            )

        console.print(table)

        # Also save table data as JSON to file
        output_file.write_text(json.dumps(flattened_resources, indent=2))
        console.print(f"[green]Data also saved to {output_file}[/green]")
    elif output_format == "md":
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
        table = Table(title="AWS Resources")
        table.add_column("Region", style="blue")
        table.add_column("Resource Name", style="cyan")
        table.add_column("Resource Family", style="magenta")
        table.add_column("Resource Type", style="yellow")
        table.add_column("Resource ID", style="green")
        table.add_column("Resource ARN", style="white")

        for resource in flattened_resources:
            table.add_row(
                resource.get("region", "N/A"),
                resource["resource_name"],
                resource["resource_family"],
                resource["resource_type"],
                resource["resource_id"],
                resource["resource_arn"],
            )

        console.print(table)

        # Also display a summary in console
        console.print("\n[bold blue]Markdown Summary Generated:[/bold blue]")
        console.print(f"Total resources: {len(flattened_resources)}")

        # Count by service family
        service_counts = Counter(r["resource_family"] for r in flattened_resources)
        for service, count in service_counts.items():
            console.print(f"  {service}: {count} resources")

    else:
        console.print(
            f"[red]Unknown output format '{output_format}'. Supported: json, table, md[/red]"
        )

    return len(flattened_resources)


def compare_with_existing(output_file: Path, new_data: Dict[str, Any]) -> None:
    """Compare new scan results with existing file to detect changes."""
    if output_file.exists():
        existing_data = json.loads(output_file.read_text())
        diff = DeepDiff(existing_data, new_data, ignore_order=True)
        if not diff:
            console.print("[green]No changes detected since last scan.[/green]")
        else:
            console.print("[yellow]Changes detected![/yellow]")
            console.print(json.dumps(diff, indent=2, default=str))
