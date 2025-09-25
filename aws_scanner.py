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
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

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

# Global shutdown flag for graceful exit
shutdown_requested = threading.Event()
# Track if shutdown message was already printed
shutdown_printed = threading.Event()

# Add the script's directory to the Python path to find modules
script_dir = Path(__file__).parent.absolute()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

app = typer.Typer()
console = Console()

# Supported services
SUPPORTED_SERVICES = ["ec2", "s3", "ecs", "elb", "vpc", "autoscaling"]

# Thread-safe session pool for connection reuse
_session_pool: Dict[str, boto3.Session] = {}
_session_pool_lock = threading.Lock()


def get_session(profile_name: Optional[str] = None) -> boto3.Session:
    """Get AWS session with thread-safe connection pooling."""
    cache_key = profile_name or "default"

    # First check if session exists (avoid lock if not needed)
    if cache_key in _session_pool:
        return _session_pool[cache_key]

    # Use lock for thread-safe session creation
    with _session_pool_lock:
        # Double-check pattern: verify session wasn't created while waiting for lock
        if cache_key not in _session_pool:
            try:
                session = boto3.Session(profile_name=profile_name)
                _session_pool[cache_key] = session
            except Exception as e:  # More generic exception handling
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

    console.print(output)
    return output


def check_and_display_cache_status(
    session: boto3.Session,
    region_list: List[str],
    services: List[str],
    tag_key: Optional[str],
    tag_value: Optional[str],
    use_cache: bool,
    all_services: bool,
) -> None:
    """Check cache status for all regions/services and display summary."""
    if not use_cache:
        return

    # Import cache function
    from aws_scanner_lib.cache import get_cached_result

    cached_items = []

    for region in region_list:
        if all_services or (tag_key or tag_value):
            # Check cross-service cache
            cached_result = get_cached_result(
                region, "all_services", tag_key, tag_value
            )
            if cached_result is not None:
                cached_items.append(f"All services in {region}")
        else:
            # Check individual service caches
            for service in services:
                cached_result = get_cached_result(region, service, tag_key, tag_value)
                if cached_result is not None:
                    cached_items.append(f"{service} in {region}")

    if cached_items:
        console.print("\n[bold cyan]💾 Cache Status:[/bold cyan]")
        for item in cached_items:
            console.print(f"[dim cyan]  ✓ Using cached result for {item}[/dim cyan]")
        console.print("")  # Add spacing after cache status


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
    all_services: bool = False,
    shutdown_event: Optional[threading.Event] = None,
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
        # Auto-detect scanning mode: Use Resource Groups API when tags are provided OR --all-services is used
        use_resource_groups_api = all_services or (tag_key or tag_value)

        if use_resource_groups_api:
            # Use Resource Groups API for cross-service scanning (when tags provided or --all-services)
            from aws_scanner_lib.scan import scan_all_services_with_tags

            future_to_region = {
                executor.submit(
                    scan_all_services_with_tags,
                    session,
                    region,
                    tag_key,
                    tag_value,
                    use_cache,
                ): region
                for region in region_list
            }
        else:
            # Use traditional service-specific scanning (when no tags provided)
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
                    shutdown_event,  # Pass shutdown event to scan_region
                ): region
                for region in region_list
            }

        # Collect results as they complete
        total_scan_time = 0.0
        completed_futures = 0

        try:
            for future in as_completed(future_to_region):
                # Check for shutdown request before processing each future
                if shutdown_event and shutdown_event.is_set():
                    console.print(
                        "[yellow]Cancelling remaining region scans...[/yellow]"
                    )
                    # Cancel all pending futures
                    for pending_future in future_to_region:
                        if not pending_future.done():
                            pending_future.cancel()
                    break

                region = future_to_region[future]
                completed_futures += 1

                try:
                    region_name, region_results, scan_duration = future.result(
                        timeout=300
                    )
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

        except KeyboardInterrupt:
            # Handle direct KeyboardInterrupt during scanning
            console.print("[yellow]Keyboard interrupt received. Cancelling...[/yellow]")
            if shutdown_event:
                shutdown_event.set()
            # Cancel all remaining futures
            for pending_future in future_to_region:
                if not pending_future.done():
                    pending_future.cancel()
            raise

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
    all_services: bool = typer.Option(
        False,
        "--all-services",
        help="Use Resource Groups API to scan ALL AWS services (requires tags). Discovers 100+ services beyond EC2/VPC/S3/etc.",
    ),
) -> None:
    """
    AWS Multi-Service Scanner

    Scan multiple AWS services across regions with optional tag filtering.
    """
    # Validate worker counts
    max_workers = max(1, min(max_workers, 20))  # Limit between 1-20
    service_workers = max(1, min(service_workers, 10))  # Limit between 1-10

    # Validate all_services mode requirements
    if all_services:
        if not tag_key and not tag_value:
            console.print(
                "[red]❌ Error: --all-services mode requires either --tag-key or --tag-value[/red]"
            )
            console.print(
                "[dim]The Resource Groups API requires tag filtering to discover resources[/dim]"
            )
            raise typer.Exit(1)
        console.print(
            "[bold cyan]🌐 Cross-Service Mode: Scanning ALL AWS services (100+ services)[/bold cyan]"
        )

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

    # Create an elegant configuration panel with centered title
    config_table = Table(show_header=False, box=None, width=80)
    config_table.add_column("Parameter", style="bold cyan", width=18)
    config_table.add_column("Value", style="bold yellow", width=60)

    # Auto-detect scanning mode for display
    use_resource_groups_api = all_services or (tag_key or tag_value)

    if use_resource_groups_api:
        if all_services:
            config_table.add_row("🌐 Mode", "All AWS Services (100+ services)")
            config_table.add_row("🔍 Discovery", "Resource Groups Tagging API")
        else:
            config_table.add_row("🌐 Mode", "Cross-Service (Tag-based)")
            config_table.add_row("🔍 Discovery", "Resource Groups Tagging API")
    else:
        config_table.add_row("🔧 Mode", "Service-Specific")
        config_table.add_row("📋 Services", f"{', '.join(services)}")

    config_table.add_row(
        "⚡ Workers", f"{max_workers} regions × {service_workers} services"
    )
    config_table.add_row("💾 Caching", "✅ Enabled" if use_cache else "❌ Disabled")

    if refresh:
        config_table.add_row("🔄 Refresh", f"Every {refresh_interval}s")

    if tag_key and tag_value:
        config_table.add_row("🏷️  Tag Filter", f"{tag_key}={tag_value}")
    elif tag_key:
        config_table.add_row("🏷️  Tag Filter", f"{tag_key}=*")

    config_table.add_row("📄 Output", output_format.upper())

    # Add AWS Profile information
    aws_profile = os.environ.get("AWS_PROFILE", "default")
    config_table.add_row("👤 AWS Profile", aws_profile)

    # Center the title and create a more compact panel
    console.print(
        Panel(
            config_table,
            title="[bold white]⚙️  Configuration[/bold white]",
            title_align="center",
            border_style="bright_blue",
            padding=(0, 1),
            width=86,
        )
    )

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

    # Create regions panel with more compact layout
    regions_display: Union[str, Table]
    if len(region_list) <= 4:
        # Show regions in a single row for small lists
        regions_display = "  ".join([f"{region}" for region in region_list])
    else:
        # Show regions in multiple columns for larger lists
        regions_table = Table(show_header=False, box=None, width=80)
        regions_table.add_column("", style="bold green", width=25)
        regions_table.add_column("", style="bold green", width=25)
        regions_table.add_column("", style="bold green", width=25)

        # Add regions in groups of 3
        for i in range(0, len(region_list), 3):
            row_regions = region_list[i : i + 3]
            row = [
                f"{row_regions[j]}" if j < len(row_regions) else "" for j in range(3)
            ]
            if len(row_regions) > 0:
                regions_table.add_row(
                    row[0],
                    row[1] if len(row) > 1 else "",
                    row[2] if len(row) > 2 else "",
                )

        regions_display = regions_table

    console.print(
        Panel(
            regions_display,
            title=f"[bold white]📍 Target Regions ({len(region_list)})[/bold white]",
            title_align="center",
            border_style="bright_green",
            padding=(0, 1),
            width=86,
        )
    )

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

    # Set up signal handler for graceful exit (works for both single scan and refresh mode)
    def signal_handler(signum: int, frame: Any) -> None:
        if not shutdown_requested.is_set():
            shutdown_requested.set()
            shutdown_printed.set()
            console.print("\n\n[yellow]Graceful shutdown requested...[/yellow]")
            console.print("[dim]Stopping ongoing operations and cleaning up...[/dim]")
        else:
            # If shutdown already requested, force exit on second Ctrl+C
            console.print(
                "\n[red]Force exit requested. Terminating immediately...[/red]"
            )
            sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize refresh mode variables
    scan_count = 0
    total_scan_time = 0.0

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
                f"[bold blue]🔄 Starting scan #{scan_count}{'...' if scan_count == 1 else ' (refresh mode)'}[/bold blue]"
            )
        else:
            # More descriptive message based on scan type
            if use_resource_groups_api:
                if all_services:
                    console.print(
                        "\n[bold blue]🌐 Scanning ALL AWS services across regions...[/bold blue]"
                    )
                else:
                    console.print(
                        f"\n[bold blue]🏷️  Scanning tagged resources across {len(region_list)} region{'s' if len(region_list) > 1 else ''}...[/bold blue]"
                    )
            else:
                console.print(
                    f"\n[bold blue]🔧 Scanning {len(services)} service{'s' if len(services) > 1 else ''} across {len(region_list)} region{'s' if len(region_list) > 1 else ''}...[/bold blue]"
                )

        # Check for shutdown before starting scan
        if shutdown_requested.is_set():
            console.print("[yellow]Scan cancelled before starting[/yellow]")
            break

        # Check and display cache status before starting scan
        check_and_display_cache_status(
            session, region_list, services, tag_key, tag_value, use_cache, all_services
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
                all_services,
                shutdown_requested,
            )

        scan_duration = time.time() - start_time
        total_scan_time += scan_duration

        # Check for shutdown after scan completes
        if shutdown_requested.is_set():
            console.print("[yellow]Scan interrupted during execution[/yellow]")
            if scan_count == 1:
                console.print(
                    f"[dim]Partial scan completed in {scan_duration:.1f}s[/dim]"
                )
            break

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

            # Check for shutdown before processing results
            if shutdown_requested.is_set():
                console.print(
                    "[yellow]Skipping output generation due to shutdown request[/yellow]"
                )
                break

            # Compare with existing results if requested (only on first scan)
            if compare and scan_count == 1:
                compare_with_existing(current_output_file, all_results)

            # Check for shutdown before output generation
            if shutdown_requested.is_set():
                console.print(
                    "[yellow]Skipping output generation due to shutdown request[/yellow]"
                )
                break

            # Output results
            if not refresh or scan_count == 1:
                console.print("\n[bold green]Generating output...[/bold green]")

            resource_count = output_results(
                all_results, current_output_file, output_format
            )

            # Show scan completion status

            if refresh:
                console.print(
                    f"\n[bold green]🎉 Scan #{scan_count} completed![/bold green]"
                )
                console.print(
                    f"[green]📊 Found {resource_count} resources across {len(all_results)} region{'s' if len(all_results) > 1 else ''} in {scan_duration:.1f}s[/green]"
                )
                console.print(
                    "[dim cyan]💡 Press Ctrl+C to stop refresh mode[/dim cyan]"
                )
            else:
                console.print(
                    "\n[bold green]🎉 Scan completed successfully![/bold green]"
                )
                console.print(
                    f"[green]📊 Found {resource_count} resources across {len(all_results)} region{'s' if len(all_results) > 1 else ''} in {scan_duration:.1f}s[/green]"
                )

        # Exit if not in refresh mode
        if not refresh:
            break

        # Exit immediately if shutdown was requested
        if shutdown_requested.is_set():
            console.print(
                f"[yellow]Scan stopped after {scan_count} {'scan' if scan_count == 1 else 'scans'}[/yellow]"
            )
            console.print(f"[dim]Total runtime: {total_scan_time:.1f}s[/dim]")
            break

        # Wait for next refresh or stop if requested
        if refresh and not shutdown_requested.is_set():
            console.print(f"[dim]Waiting {refresh_interval}s until next scan...[/dim]")

            # Interruptible sleep
            for _ in range(refresh_interval):
                time.sleep(1)
                if shutdown_requested.is_set():
                    break

        # Exit if stop was requested during wait
        if shutdown_requested.is_set():
            console.print(
                f"[yellow]Refresh mode stopped after {scan_count} scans[/yellow]"
            )
            console.print(f"[dim]Total runtime: {total_scan_time:.1f}s[/dim]")
            break


if __name__ == "__main__":
    app()
