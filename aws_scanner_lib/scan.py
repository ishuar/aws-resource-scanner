"""
Scan module for AWS Scanner

Handles scanning operations for AWS services across regions.
"""

import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict, Any, Tuple
from rich.console import Console
import boto3
import botocore
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

# Import cache functions
from .cache import get_cached_result, cache_result

# Import service scanners
from services import (
    scan_ec2,
    scan_s3,
    scan_ecs,
    scan_elb,
    scan_vpc,
    scan_autoscaling,
)

console = Console()

# Supported services
SUPPORTED_SERVICES = ["ec2", "s3", "ecs", "elb", "vpc", "autoscaling"]


def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1):
    """Retry function with exponential backoff for transient errors."""
    for attempt in range(max_retries):
        try:
            return func()
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")

            # Don't retry for non-transient errors
            if error_code in [
                "AccessDenied",
                "UnauthorizedOperation",
                "InvalidUserID.NotFound",
            ]:
                raise e

            # Retry for transient errors
            if error_code in [
                "Throttling",
                "ThrottlingException",
                "RequestLimitExceeded",
                "ServiceUnavailable",
            ]:
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt) + random.uniform(0, 1)
                    console.print(
                        f"[yellow]Retrying in {delay:.1f}s due to {error_code}[/yellow]"
                    )
                    time.sleep(delay)
                    continue
            raise e
        except (EndpointConnectionError, botocore.exceptions.ConnectTimeoutError) as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt) + random.uniform(0, 1)
                console.print(f"[yellow]Retrying connection in {delay:.1f}s[/yellow]")
                time.sleep(delay)
                continue
            raise e


def scan_service(
    session: boto3.Session,
    region: str,
    service: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Route service scan to appropriate modular scanner with improved error handling and caching."""

    # Check cache first
    if use_cache:
        cached_result = get_cached_result(region, service, tag_key, tag_value)
        if cached_result is not None:
            console.print(f"    Using cached result for {service} in {region}")
            return cached_result

    def _do_scan():
        if service == "ec2":
            return scan_ec2(session, region, tag_key, tag_value)
        elif service == "s3":
            return scan_s3(session, region, tag_key, tag_value)
        elif service == "ecs":
            return scan_ecs(session, region, tag_key, tag_value)
        elif service == "elb":
            return scan_elb(session, region, tag_key, tag_value)
        elif service == "vpc":
            return scan_vpc(session, region, tag_key, tag_value)
        elif service == "autoscaling":
            return scan_autoscaling(session, region, tag_key, tag_value)
        else:
            console.print(
                f"[yellow]Service scan for '{service}' not implemented yet.[/yellow]"
            )
            return {}

    try:
        result = retry_with_backoff(_do_scan)

        # Cache the result
        if use_cache and result:
            cache_result(region, service, result, tag_key, tag_value)

        return result
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        console.print(
            f"[red]AWS API Error for {service} in {region}: {error_code} - {e}[/red]"
        )
        return {}
    except EndpointConnectionError as e:
        console.print(f"[red]Connection Error for {service} in {region}: {e}[/red]")
        return {}
    except NoCredentialsError as e:
        console.print(f"[red]Credentials Error for {service} in {region}: {e}[/red]")
        return {}
    except Exception as e:
        console.print(
            f"[red]Unexpected error scanning {service} in {region}: {e}[/red]"
        )
        return {}


def scan_region(
    session: boto3.Session,
    region: str,
    services: List[str],
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
    service_workers: int = 4,
    use_cache: bool = True,
    progress_callback=None,
) -> Tuple[str, Dict[str, Any], float]:
    """Scan all services in a single region with parallel service scanning."""
    start_time = time.time()
    region_results = {}

    # Limit workers to reasonable bounds
    max_service_workers = min(len(services), max(1, min(service_workers, 10)))

    with ThreadPoolExecutor(max_workers=max_service_workers) as executor:
        # Submit service scanning tasks
        future_to_service = {
            executor.submit(
                scan_service, session, region, service, tag_key, tag_value, use_cache
            ): service
            for service in services
            if service in SUPPORTED_SERVICES
        }

        # Collect results as they complete
        service_results_summary = {}
        completed_services = 0
        total_services = len(future_to_service)

        for future in as_completed(future_to_service):
            service = future_to_service[future]
            try:
                service_data = future.result(
                    timeout=60
                )  # 60 second timeout per service
                if service_data:
                    region_results[service] = service_data
                    # Count resources for feedback
                    total_resources = sum(
                        len(v) if isinstance(v, list) else 1
                        for v in service_data.values()
                    )
                    service_results_summary[service] = total_resources
                else:
                    service_results_summary[service] = 0
            except Exception as e:
                console.print(
                    f"[red]    Error scanning {service} in {region}: {e}[/red]"
                )
                service_results_summary[service] = 0

            # Update progress if callback provided
            completed_services += 1
            if progress_callback:
                progress_callback(completed_services, total_services, service, region)

    # Print grouped results for this region in clean tabular format
    if service_results_summary:
        # Calculate total resources
        total_resources = sum(service_results_summary.values())

        # Create clean tabular output
        output_lines = [f"\n{region.upper()}:"]
        output_lines.append("┌─────────────┬───────┐")
        output_lines.append("│ Service     │ Count │")
        output_lines.append("├─────────────┼───────┤")

        for service, count in service_results_summary.items():
            output_lines.append(f"│ {service.upper():<11} │ {count:>5} │")

        output_lines.append("├─────────────┼───────┤")
        output_lines.append(f"│ {'TOTAL':<11} │ {total_resources:>5} │")
        output_lines.append("└─────────────┴───────┘")

        print("\n".join(output_lines), file=__import__("sys").stderr, flush=True)

    # Calculate and display region scan time
    end_time = time.time()
    scan_duration = end_time - start_time
    print(
        f"Region {region} scan completed in {scan_duration:.1f}s\n",
        file=__import__("sys").stderr,
        flush=True,
    )

    return region, region_results, scan_duration
