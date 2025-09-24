#!/usr/bin/env python3
"""
AWS Multi-Service Scanner (Modular Version)
-------------------------------------------

Scans across multiple AWS service families with optional tag-based filtering,
supports multiple regions, and outputs results in JSON or table format.

This version uses modular service scanners for better code organization.
"""
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import boto3
import botocore
import botocore.config
import pyfiglet
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

# Import modular components
from aws_scanner_lib.outputs import compare_with_existing, output_results
from aws_scanner_lib.scan import scan_region

# Add the script's directory to the Python path to find modules
script_dir = Path(__file__).parent.absolute()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

app = typer.Typer()
console = Console()

# Supported services
SUPPORTED_SERVICES = ["ec2", "s3", "ecs", "elb", "vpc", "autoscaling"]

# Session pool for connection reuse
_session_pool = {}


def get_session(profile_name: Optional[str] = None) -> boto3.Session:
    """Get AWS session with connection pooling."""
    cache_key = profile_name or "default"

    if cache_key not in _session_pool:
        try:
            session = boto3.Session(profile_name=profile_name)
            _session_pool[cache_key] = session
        except botocore.exceptions.ProfileNotFound as e:
            console.print(
                f"[red]Error: AWS profile '{profile_name}' not found.\n'{e}'[/red]"
            )
            raise typer.Exit(1)

    return _session_pool[cache_key]


def get_client_with_config(
    session: boto3.Session, service_name: str, region_name: str
) -> Any:
    """Get AWS client with optimized configuration."""
    config = botocore.config.Config(
        max_pool_connections=50,  # Increase connection pool size
        retries={"max_attempts": 3, "mode": "adaptive"},  # Built-in retry
        read_timeout=60,
        connect_timeout=10,
    )
    return session.client(service_name, region_name=region_name, config=config)


def display_banner() -> str:
    """Display fancy ASCII banner with AWS profile information."""
    # Create fancy ASCII banner
    try:
        banner = pyfiglet.figlet_format("AWS Scanner", font="slant")
        output = f"[bold cyan]{banner}[/bold cyan]"
    except (pyfiglet.FontNotFound, pyfiglet.FigletError, OSError):
        # Fallback if pyfiglet fails
        output = "[bold cyan]╔═══════════════════════════════════════════════════════════╗[/bold cyan]\n"
        output += "[bold cyan]║                   AWS SERVICE SCANNER                    ║[/bold cyan]\n"
        output += "[bold cyan]╚═══════════════════════════════════════════════════════════╝[/bold cyan]"

    output += "\n[dim]Modular Version with Advanced Optimizations[/dim]\n"

    # Display AWS Profile information
    aws_profile = os.environ.get("AWS_PROFILE", "default")
    output += f"AWS Profile: [bold yellow]{aws_profile}[/bold yellow]"

    console.print(output)
    return output


def perform_scan(
    session: boto3.Session,
    region_list: List[str],
    services: List[str],
    tag_key: Optional[str],
    tag_value: Optional[str],
    max_workers: int,
    service_workers: int,
    use_cache: bool,
    progress: Optional[Progress] = None,
) -> Dict[str, Dict[str, Any]]:
    """Perform the AWS scanning operation with optional progress reporting."""
    all_results = {}
    main_task = None
    region_tasks = {}

    if progress:
        # Main progress bar for overall region completion
        main_task = progress.add_task(
            f"🔍 Scanning {len(region_list)} regions", total=len(region_list)
        )

        def create_progress_callback(
            region_name: str,
        ) -> Callable[[int, int, str, str], None]:
            """Create a progress callback function for a specific region"""

            def update_progress(
                completed: int, total: int, service: str, region: str
            ) -> None:
                if region_name not in region_tasks:
                    region_tasks[region_name] = progress.add_task(
                        f"  📍 {region_name}", total=total
                    )
                progress.update(
                    region_tasks[region_name],
                    completed=completed,
                    description=f"  📍 {region_name} ({service})",
                )

            return update_progress

    else:

        def create_progress_callback(
            region_name: str,
        ) -> Callable[[int, int, str, str], None]:
            return lambda *args: None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit region scanning tasks with progress callbacks
        future_to_region = {
            executor.submit(
                scan_region,
                session,
                region,
                services,
                tag_key,
                tag_value,
                service_workers,
                use_cache,
                create_progress_callback(region),
            ): region
            for region in region_list
        }

        # Collect results as they complete
        total_scan_time = 0.0
        for future in as_completed(future_to_region):
            region = future_to_region[future]
            try:
                region_name, region_results, scan_duration = future.result(timeout=300)
                total_scan_time += scan_duration
                if region_results:
                    all_results[region_name] = region_results
                    if progress and main_task is not None:
                        # Update the region task to show completion
                        if region_name in region_tasks:
                            progress.update(
                                region_tasks[region_name],
                                description=f"  ✅ {region_name}",
                                completed=progress.tasks[
                                    region_tasks[region_name]
                                ].total,
                            )
                        console.print(
                            f"[green]✅ Completed scanning {region_name}[/green]"
                        )
                else:
                    if progress and main_task is not None:
                        # Update the region task to show no resources
                        if region_name in region_tasks:
                            progress.update(
                                region_tasks[region_name],
                                description=f"  ⚪ {region_name} (no resources)",
                                completed=progress.tasks[
                                    region_tasks[region_name]
                                ].total,
                            )
                        console.print(
                            f"[dim yellow]⚪ No resources found in {region_name}[/dim yellow]"
                        )
            except Exception as e:
                if progress and main_task is not None:
                    # Update the region task to show error
                    if region in region_tasks:
                        progress.update(
                            region_tasks[region],
                            description=f"  ❌ {region}",
                            completed=progress.tasks[region_tasks[region]].total,
                        )
                console.print(f"[red]❌ Failed to scan {region}: {e}[/red]")
            finally:
                if progress and main_task is not None:
                    progress.advance(main_task)

    return all_results


@app.command()
def main(
    regions: Optional[str] = typer.Option(
        None, "--regions", "-r", help="Comma-separated AWS regions to scan"
    ),
    services: List[str] = typer.Option(
        SUPPORTED_SERVICES, "--service", "-s", help="AWS services to scan"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="AWS profile to use"
    ),
    tag_key: Optional[str] = typer.Option(None, "--tag-key", help="Filter by tag key"),
    tag_value: Optional[str] = typer.Option(
        None, "--tag-value", help="Filter by tag value"
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path. If not provided, a dynamic name will be generated.",
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (json|table|md)"
    ),
    compare: bool = typer.Option(
        False, "--compare", "-c", help="Compare with existing results"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be scanned without executing"
    ),
    max_workers: int = typer.Option(
        8,
        "--max-workers",
        "-w",
        help="Maximum number of parallel workers for region scanning (1-20)",
    ),
    service_workers: int = typer.Option(
        4,
        "--service-workers",
        help="Maximum number of parallel workers for service scanning within each region (1-10)",
    ),
    use_cache: bool = typer.Option(
        True,
        "--cache/--no-cache",
        help="Enable/disable caching of scan results (TTL: 10 minutes)",
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh/--no-refresh",
        help="Enable continuous refresh mode to update results periodically",
    ),
    refresh_interval: int = typer.Option(
        10,
        "--refresh-interval",
        "-i",
        help="Refresh interval in seconds (default: 10, min: 5, max: 300)",
    ),
) -> None:
    """
    AWS Multi-Service Scanner

    Scan multiple AWS services across regions with optional tag filtering.
    """
    # Validate worker counts
    max_workers = max(1, min(max_workers, 20))  # Limit between 1-20
    service_workers = max(1, min(service_workers, 10))  # Limit between 1-10

    # Validate refresh parameters
    refresh_interval = max(5, min(refresh_interval, 300))  # Limit between 5-300 seconds

    # Refresh mode validation
    if refresh and dry_run:
        console.print(
            "[red]❌ Cannot use refresh mode with dry run. Please choose one.[/red]"
        )
        raise typer.Exit(1)

    if refresh and compare:
        console.print(
            "[red]❌ Cannot use refresh mode with compare. Please choose one.[/red]"
        )
        raise typer.Exit(1)

    # Disable cache when refresh mode is enabled to ensure fresh data
    if refresh:
        use_cache = False

    # Display banner
    display_banner()

    # Create an elegant configuration panel
    config_table = Table(title="Configuration", show_header=False, box=None)
    config_table.add_column("Parameter", style="bold cyan", width=20)
    config_table.add_column("Value", style="bold yellow")

    config_table.add_row("Services", f"{', '.join(services)}")
    config_table.add_row(
        "Workers", f"{max_workers} regions, {service_workers} services/region"
    )
    config_table.add_row("Caching", "Enabled" if use_cache else "Disabled")
    config_table.add_row("Refresh Mode", "Enabled" if refresh else "Disabled")
    if refresh:
        config_table.add_row("Refresh Interval", f"{refresh_interval}s")
    if tag_key and tag_value:
        config_table.add_row("Tag Filter", f"{tag_key}={tag_value}")
    config_table.add_row("Output Format", output_format.upper())

    console.print(Panel(config_table, border_style="bright_blue", padding=(1, 2)))

    # List of all AWS Europe and US regions
    default_europe_us_regions = [
        "eu-north-1",
        "eu-west-1",
        "eu-west-2",
        "eu-west-3",
        "eu-central-1",
        "us-east-1",
        "us-east-2",
        "us-west-1",
        "us-west-2",
    ]
    if not regions:
        region_list = default_europe_us_regions
        console.print(
            "[dim yellow]ℹ️ No regions specified. Scanning all Europe and US regions.[/dim yellow]"
        )
    else:
        region_list = [r.strip() for r in regions.split(",") if r.strip()]

    # Create regions panel
    regions_table = Table(title="Target Regions", show_header=False, box=None)
    regions_table.add_column("Region", style="bold green")
    for i, region in enumerate(region_list, 1):
        regions_table.add_row(region)

    console.print(Panel(regions_table, border_style="bright_green", padding=(1, 2)))

    session = get_session(profile)

    # Handle dry run
    if dry_run:
        console.print(
            "\n[bold yellow]🔍 DRY RUN MODE - No actual scanning will be performed[/bold yellow]"
        )
        console.print("\n[bold blue]Scan Plan:[/bold blue]")
        console.print(f"  • [bold]Regions to scan:[/bold] {len(region_list)}")
        for i, region in enumerate(region_list, 1):
            console.print(f"    {i}. {region}")

        console.print(
            f"\n  • [bold]Services to scan per region:[/bold] {len(services)}"
        )
        for i, service in enumerate(services, 1):
            console.print(f"    {i}. {service}")

        console.print(
            f"\n  • [bold]Total operations:[/bold] {len(region_list)} × {len(services)} = {len(region_list) * len(services)} service scans"
        )

        if tag_key and tag_value:
            console.print(f"  • [bold]Tag filtering:[/bold] {tag_key}={tag_value}")
        else:
            console.print("  • [bold]Tag filtering:[/bold] None (all resources)")

        console.print(
            f"  • [bold]Parallel workers:[/bold] {max_workers} regions, {service_workers} services per region"
        )
        console.print(
            f"  • [bold]Caching:[/bold] {'Enabled' if use_cache else 'Disabled'}"
        )
        console.print(f"  • [bold]Output format:[/bold] {output_format}")

        if output_file:
            console.print(f"  • [bold]Output file:[/bold] {output_file}")
        else:
            console.print("  • [bold]Output file:[/bold] Auto-generated")

        console.print(
            "\n[bold green]✅ Dry run completed. Use without --dry-run to execute the actual scan.[/bold green]"
        )
        return

    # Initialize refresh mode variables
    scan_count = 0
    total_scan_time = 0.0

    # Set up signal handler for graceful exit in refresh mode
    stop_refresh = False

    def signal_handler(signum: int, frame: Any) -> None:
        nonlocal stop_refresh
        stop_refresh = True
        console.print("\n\n[yellow]Graceful shutdown requested...[/yellow]")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Main scanning loop (single scan or refresh mode)
    while True:
        scan_count += 1
        start_time = time.time()

        # Clear screen for refresh mode (but not first scan)
        if refresh and scan_count > 1:
            console.clear()
            display_banner()
            console.print(f"[bold cyan]Refresh Mode - Scan #{scan_count}[/bold cyan]")
            console.print(
                f"[dim]Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}[/dim]\n"
            )

        if refresh:
            console.print(
                f"[bold blue]Starting scan #{scan_count}{'...' if scan_count == 1 else ' (refresh mode)'}[/bold blue]"
            )
        else:
            console.print(
                "\n[bold blue]Starting parallel region scanning...[/bold blue]"
            )

        # Perform the scan with progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            all_results = perform_scan(
                session,
                region_list,
                services,
                tag_key,
                tag_value,
                max_workers,
                service_workers,
                use_cache,
                progress,
            )

        scan_duration = time.time() - start_time
        total_scan_time += scan_duration

        if not all_results:
            console.print(
                "[yellow]⚪ No resources found matching the criteria.[/yellow]"
            )
            if not refresh:
                return
        else:
            # Dynamically generate output file name if not provided
            if output_file is None:
                parts = ["aws-resources"]
                if tag_key:
                    parts.append(str(tag_key))
                if tag_value:
                    parts.append(str(tag_value))
                # If only one region and one service, include them
                if len(region_list) == 1:
                    parts.append(region_list[0])
                if len(services) == 1:
                    parts.append(services[0])
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                filename = "-".join(parts) + f"-{timestamp}.json"
                current_output_file = Path(f"/tmp/aws_resource_scanner/{filename}")
            else:
                current_output_file = output_file

            # Compare with existing results if requested (only on first scan)
            if compare and scan_count == 1:
                compare_with_existing(current_output_file, all_results)

            # Output results
            if not refresh or scan_count == 1:
                console.print("\n[bold green]Generating output...[/bold green]")

            resource_count = output_results(
                all_results, current_output_file, output_format
            )

            # Show scan completion status

            if refresh:
                console.print(
                    f"\n[bold green]Scan #{scan_count} completed![/bold green]"
                )
                console.print(
                    f"[dim]Found {resource_count} resources across {len(all_results)} regions in {scan_duration:.1f}s[/dim]"
                )
                console.print("[dim cyan]Press Ctrl+C to stop refresh mode[/dim cyan]")
            else:
                console.print("\n[bold green]Scan completed successfully![/bold green]")
                console.print(
                    f"[dim]Found {resource_count} resources across {len(all_results)} regions in {scan_duration:.1f}s[/dim]"
                )

        # Exit if not in refresh mode
        if not refresh:
            break

        # Wait for next refresh or stop if requested
        if refresh and not stop_refresh:
            console.print(f"[dim]Waiting {refresh_interval}s until next scan...[/dim]")

            # Interruptible sleep
            for _ in range(refresh_interval):
                time.sleep(1)
                if stop_refresh:
                    pass

        # Exit if stop was requested
        if stop_refresh:
            console.print(
                f"[yellow]Refresh mode stopped after {scan_count} scans[/yellow]"
            )
            console.print(f"[dim]Total runtime: {total_scan_time:.1f}s[/dim]")
            break


if __name__ == "__main__":
    app()
