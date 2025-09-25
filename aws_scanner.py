"""
AWS Multi-Service Scanner (Core Module)
--------------------------------------

Core functionality for scanning AWS resources across multiple services and regions.
This module provides the business logic for AWS resource discovery, caching,
and result processing, separated from CLI concerns.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional

import boto3
import botocore
import botocore.config
import pyfiglet
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    ProfileNotFound,
    TokenRetrievalError,
)
from rich.console import Console
from rich.progress import Progress

# Import modular components
from aws_scanner_lib.scan import scan_region

# Global components
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
            except ProfileNotFound as e:
                raise RuntimeError(f"AWS profile '{profile_name}' not found") from e
            except Exception as e:  # More generic exception handling
                raise RuntimeError(f"Failed to create AWS session: {e}") from e

    return _session_pool[cache_key]


def validate_aws_credentials(
    session: boto3.Session, profile_name: Optional[str] = None
) -> tuple[bool, str]:
    """
    Validate AWS credentials by attempting to call STS get-caller-identity.

    Returns:
        tuple: (is_valid, message)
    """
    try:
        # Try to get caller identity to validate credentials
        sts_client = session.client("sts")
        response = sts_client.get_caller_identity()

        # Extract account info
        account_id = response.get("Account", "Unknown")
        user_arn = response.get("Arn", "Unknown")

        return (
            True,
            f"✅ AWS credentials valid (Account: {account_id}, User: {user_arn.split('/')[-1]})",
        )

    except NoCredentialsError:
        profile_msg = f" for profile '{profile_name}'" if profile_name else ""
        return (
            False,
            f"❌ No AWS credentials found{profile_msg}. Please configure AWS credentials or set AWS_PROFILE environment variable.",
        )

    except TokenRetrievalError:
        return (
            False,
            "❌ Failed to retrieve AWS credentials. Check your AWS CLI configuration or SSO session.",
        )

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code in ["InvalidUserID.NotFound", "AccessDenied"]:
            return False, f"❌ AWS credentials invalid or expired: {e}"
        return False, f"❌ AWS API error: {e}"

    except Exception as e:
        return False, f"❌ Unexpected error validating credentials: {e}"


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
    region_list: List[str],
    services: List[str],
    tag_key: Optional[str],
    tag_value: Optional[str],
    use_cache: bool,
    all_services: bool,
) -> bool:
    """
    Check cache status for all regions/services and display summary.

    Returns:
        bool: True if any cached results are found, False otherwise
    """
    if not use_cache:
        return False

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
        from rich.panel import Panel
        from rich.table import Table

        # Create cache status table
        cache_table = Table(show_header=False, box=None, width=80)
        cache_table.add_column("", style="dim cyan", width=80)

        for item in cached_items:
            cache_table.add_row(f"✓ Using cached result for {item}")

        console.print(
            Panel(
                cache_table,
                title="[bold cyan]💾 Cache Status[/bold cyan]",
                title_align="center",
                border_style="cyan",
                padding=(0, 1),
                width=86,
            )
        )
        console.print(
            "[dim yellow]⚠️  Note: Results may include cached data. For real-time results, disable caching with --no-cache[/dim yellow]\n"
        )
        return True

    return False


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
