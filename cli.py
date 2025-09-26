#!/usr/bin/env python3
"""
AWS Multi-Service Scanner CLI
----------------------------

Command-line interface for scanning AWS resources across multiple services and regions.
This module contains all CLI logic separated from core business functionality.
"""

import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, List, Optional, Union

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

# Import core business logic functions
from aws_scanner import (
    SUPPORTED_SERVICES,
    check_and_display_cache_status,
    display_banner,
    display_region_summaries,
    get_session,
    perform_scan,
    validate_aws_credentials,
)

# Import core scanning functionality
from aws_scanner_lib.outputs import (
    TABLE_MINIMUM_WIDTH,
    compare_with_existing,
    output_results,
)

# Global shutdown flag for graceful exit
shutdown_requested = threading.Event()
# Track if shutdown message was already printed
shutdown_printed = threading.Event()

# Add the script's directory to the Python path to find modules
script_dir = Path(__file__).parent.absolute()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Create the CLI application
app = typer.Typer(
    name="aws-scanner",
    help="AWS Multi-Service Scanner\n\nScan multiple AWS services across regions with optional tag filtering\n\nUse the 'scan' command to start scanning AWS resources.",
    add_completion=True,
)
console = Console()


@app.callback()
def main(ctx: typer.Context) -> None:
    """
    AWS Multi-Service Scanner
    A comprehensive tool for scanning AWS resources across multiple services and regions
    with advanced filtering, caching, and output capabilities.
    Features:
    • Multi-service scanning (EC2, S3, VPC, ECS, ELB, Auto Scaling)
    • Cross-region resource discovery
    • Tag-based filtering with Resource Groups API
    • Intelligent caching system (10-minute TTL)
    • Multiple output formats (JSON, Table, Markdown)
    • Real-time progress tracking
    • Graceful interrupt handling
    • AWS credential validation

    Use the 'scan' command to start scanning AWS resources.
    """
    pass


@app.command(name="scan")
def scan_command(
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
        "table", "--format", "-f", help="Output format (json|table|md|markdown)"
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

    Scan multiple AWS services across regions with optional tag filtering.Use the 'scan' command to start scanning AWS resources.
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

    # Create configuration panel
    _display_configuration_panel(
        all_services,
        tag_key,
        tag_value,
        services,
        max_workers,
        service_workers,
        use_cache,
        refresh,
        refresh_interval,
        output_format,
    )

    # Handle regions
    region_list = _handle_regions(regions)

    # Display regions panel
    _display_regions_panel(region_list)

    # Check and display cache status prominently if caching is enabled
    if use_cache:
        has_cache_hits = check_and_display_cache_status(
            region_list, services, tag_key, tag_value, use_cache, all_services
        )
        if has_cache_hits:
            console.print(
                "[dim]Results will be a combination of cached and real-time data.[/dim]"
            )

    # Get AWS session and validate credentials
    try:
        session = get_session(profile)

        # Validate AWS credentials before proceeding
        credentials_valid, credential_message = validate_aws_credentials(
            session, profile
        )

        if not credentials_valid:
            console.print(f"\n[red]{credential_message}[/red]")
            console.print("\n[yellow]💡 Possible solutions:[/yellow]")
            console.print("   • [dim]Configure AWS credentials: aws configure[/dim]")
            console.print(
                "   • [dim]Set AWS profile: export AWS_PROFILE=your-profile[/dim]"
            )
            console.print(
                "   • [dim]Use AWS SSO: aws sso login --profile your-profile[/dim]"
            )
            console.print(
                "   • [dim]Check existing profiles: aws configure list-profiles[/dim]"
            )

            # Check if there are cached results that could be shown
            if use_cache:
                console.print("\n[cyan]💾 Checking for cached results...[/cyan]")
                has_cache = _check_cache_availability(
                    region_list, services, tag_key, tag_value, all_services
                )
                if has_cache:
                    console.print(
                        "[yellow]⚠️  Found cached results from previous scans.[/yellow]"
                    )
                    console.print(
                        "[dim]Note: Cached data may be outdated. Set up AWS credentials for real-time results.[/dim]"
                    )
                else:
                    console.print("[red]❌ No cached results available.[/red]")
                    raise typer.Exit(1)
            else:
                raise typer.Exit(1)
        else:
            console.print(f"\n[green]{credential_message}[/green]")

    except RuntimeError as e:
        console.print(f"\n[red]❌ AWS Session Error: {e}[/red]")
        console.print(
            "\n[yellow]💡 Please check your AWS configuration and try again.[/yellow]"
        )
        raise typer.Exit(1)

    # Handle dry run
    if dry_run:
        _handle_dry_run(
            region_list,
            services,
            tag_key,
            tag_value,
            max_workers,
            service_workers,
            use_cache,
            output_format,
            output_file,
        )
        return

    # Set up signal handler for graceful exit
    _setup_signal_handlers()

    # Initialize refresh mode variables
    scan_count = 0
    total_scan_time = 0.0

    # Main scanning loop (single scan or refresh mode)
    while True:
        scan_count += 1
        start_time = time.time()

        # Handle refresh mode display
        if refresh and scan_count > 1:
            console.clear()
            display_banner()
            console.print(f"[bold cyan]Refresh Mode - Scan #{scan_count}[/bold cyan]")
            console.print(
                f"[dim]Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}[/dim]\n"
            )

        # Display scan start message
        _display_scan_start_message(
            refresh, scan_count, all_services, tag_key, tag_value, services, region_list
        )

        # Check for shutdown before starting scan
        if shutdown_requested.is_set():
            console.print("[yellow]Scan cancelled before starting[/yellow]")
            break

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

        # Handle scan results
        if not all_results:
            console.print(
                "[yellow]⚪ No resources found matching the criteria.[/yellow]"
            )
            if not refresh:
                return
        else:
            # Display region summaries after scanning is complete
            display_region_summaries(all_results)

            # Process results
            current_output_file = _generate_output_filename(
                output_file, tag_key, tag_value, region_list, services
            )

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
            _display_scan_completion(
                refresh, scan_count, resource_count, all_results, scan_duration
            )

        # Exit if not in refresh mode
        if not refresh:
            break

        # Handle refresh mode continuation
        if not _handle_refresh_continuation(
            refresh, scan_count, total_scan_time, refresh_interval
        ):
            break


def _display_configuration_panel(
    all_services: bool,
    tag_key: Optional[str],
    tag_value: Optional[str],
    services: List[str],
    max_workers: int,
    service_workers: int,
    use_cache: bool,
    refresh: bool,
    refresh_interval: int,
    output_format: str,
) -> None:
    """Display the configuration panel."""
    # Create an elegant configuration panel with centered title
    config_table = Table(show_header=False, box=None, min_width=TABLE_MINIMUM_WIDTH)
    config_table.add_column("Parameter", style="cyan", width=18, highlight=True)
    config_table.add_column("Value", style="yellow", width=60, highlight=True)

    # Auto-detect scanning mode for display
    use_resource_groups_api = all_services or (tag_key or tag_value)

    if use_resource_groups_api:
        if all_services:
            config_table.add_row("Mode", "All AWS Services (100+ services)")
            config_table.add_row("Discovery", "Resource Groups Tagging API")
        else:
            config_table.add_row("Mode", "Cross-Service (Tag-based)")
            config_table.add_row("Discovery", "Resource Groups Tagging API")
    else:
        config_table.add_row("Mode", "Service-Specific")
        config_table.add_row("Services", f"{', '.join(services)}")

    config_table.add_row(
        "Workers", f"{max_workers} regions × {service_workers} services"
    )
    config_table.add_row("Caching", "Enabled" if use_cache else "Disabled")

    if refresh:
        config_table.add_row("Refresh", f"Every {refresh_interval}s")

    if tag_key and tag_value:
        config_table.add_row("Tag Filter", f"{tag_key}={tag_value}")
    elif tag_key:
        config_table.add_row("Tag Filter", f"{tag_key}=*")

    config_table.add_row("Output", output_format.upper())

    # Add AWS Profile information
    aws_profile = os.environ.get("AWS_PROFILE", "default")
    config_table.add_row("AWS Profile 👤", aws_profile)

    # Center the title and create a more compact panel
    console.print(
        Panel(
            config_table,
            title="[bold white]Configuration[/bold white]",
            title_align="center",
            border_style="bright_blue",
            padding=(0, 1),
            width=TABLE_MINIMUM_WIDTH,
        )
    )


def _handle_regions(regions: Optional[str]) -> List[str]:
    """Handle region processing and return region list."""
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
            "[dim yellow]INFO: No regions specified. Scanning all Europe and US regions.\n[/dim yellow]"
        )
    else:
        region_list = [r.strip() for r in regions.split(",") if r.strip()]

    return region_list


def _display_regions_panel(region_list: List[str]) -> None:
    """Display the regions panel."""
    # Create regions panel with more compact layout
    regions_display: Union[str, Table]
    if len(region_list) <= 4:
        # Show regions in a single row for small lists
        regions_display = "  ".join([f"{region}" for region in region_list])
    else:
        # Show regions in multiple columns for larger lists
        regions_table = Table(
            show_header=False, box=None, min_width=TABLE_MINIMUM_WIDTH
        )
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
            title=f"[bold white]Target Regions:({len(region_list)})[/bold white]",
            title_align="center",
            border_style="bright_blue",
            padding=(0, 1),
            width=TABLE_MINIMUM_WIDTH,
        )
    )


def _handle_dry_run(
    region_list: List[str],
    services: List[str],
    tag_key: Optional[str],
    tag_value: Optional[str],
    max_workers: int,
    service_workers: int,
    use_cache: bool,
    output_format: str,
    output_file: Optional[Path],
) -> None:
    """Handle dry run display."""
    console.print(
        "\n[bold yellow]🔍 DRY RUN MODE - No actual scanning will be performed[/bold yellow]"
    )
    console.print("\n[bold blue]Scan Plan:[/bold blue]")
    console.print(f"  • [bold]Regions to scan:[/bold] {len(region_list)}")
    for i, region in enumerate(region_list, 1):
        console.print(f"    {i}. {region}")

    console.print(f"\n  • [bold]Services to scan per region:[/bold] {len(services)}")
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
    console.print(f"  • [bold]Caching:[/bold] {'Enabled' if use_cache else 'Disabled'}")
    console.print(f"  • [bold]Output format:[/bold] {output_format}")

    if output_file:
        console.print(f"  • [bold]Output file:[/bold] {output_file}")
    else:
        console.print("  • [bold]Output file:[/bold] Auto-generated")

    console.print(
        "\n[bold green]✅ Dry run completed. Use without --dry-run to execute the actual scan.[/bold green]"
    )


def _setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""

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


def _display_scan_start_message(
    refresh: bool,
    scan_count: int,
    all_services: bool,
    tag_key: Optional[str],
    tag_value: Optional[str],
    services: List[str],
    region_list: List[str],
) -> None:
    """Display the scan start message."""
    if refresh:
        console.print(
            f"[bold blue]🔄 Starting scan #{scan_count}{'...' if scan_count == 1 else ' (refresh mode)'}[/bold blue]"
        )
    else:
        # More descriptive message based on scan type
        use_resource_groups_api = all_services or (tag_key or tag_value)
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


def _generate_output_filename(
    output_file: Optional[Path],
    tag_key: Optional[str],
    tag_value: Optional[str],
    region_list: List[str],
    services: List[str],
) -> Path:
    """Generate output filename dynamically if not provided."""
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

    return current_output_file


def _display_scan_completion(
    refresh: bool,
    scan_count: int,
    resource_count: int,
    all_results: dict,
    scan_duration: float,
) -> None:
    """Display scan completion status."""
    if refresh:
        console.print(f"\n[bold green]🎉 Scan #{scan_count} completed![/bold green]")
        console.print(
            f"[green]📊 Found {resource_count} resources across {len(all_results)} region{'s' if len(all_results) > 1 else ''} in {scan_duration:.1f}s[/green]"
        )
        console.print("[dim cyan]💡 Press Ctrl+C to stop refresh mode[/dim cyan]")
    else:
        console.print("\n[bold green]🎉 Scan completed successfully![/bold green]")
        console.print(
            f"[green]📊 Found {resource_count} resources across {len(all_results)} region{'s' if len(all_results) > 1 else ''} in {scan_duration:.1f}s[/green]"
        )


def _check_cache_availability(
    region_list: List[str],
    services: List[str],
    tag_key: Optional[str],
    tag_value: Optional[str],
    all_services: bool,
) -> bool:
    """Check if cached results are available for the given parameters."""
    from aws_scanner_lib.cache import get_cached_result

    for region in region_list:
        if all_services or (tag_key or tag_value):
            # Check cross-service cache
            cached_result = get_cached_result(
                region, "all_services", tag_key, tag_value
            )
            if cached_result is not None:
                return True
        else:
            # Check individual service caches
            for service in services:
                cached_result = get_cached_result(region, service, tag_key, tag_value)
                if cached_result is not None:
                    return True
    return False


def _handle_refresh_continuation(
    refresh: bool, scan_count: int, total_scan_time: float, refresh_interval: int
) -> bool:
    """Handle refresh mode continuation. Returns True to continue, False to break."""
    # Exit immediately if shutdown was requested
    if shutdown_requested.is_set():
        console.print(
            f"[yellow]Scan stopped after {scan_count} {'scan' if scan_count == 1 else 'scans'}[/yellow]"
        )
        console.print(f"[dim]Total runtime: {total_scan_time:.1f}s[/dim]")
        return False

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
        console.print(f"[yellow]Refresh mode stopped after {scan_count} scans[/yellow]")
        console.print(f"[dim]Total runtime: {total_scan_time:.1f}s[/dim]")
        return False

    return True


if __name__ == "__main__":
    app()
