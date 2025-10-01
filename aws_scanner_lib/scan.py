"""
Scan module for AWS Scanner

Handles scanning operations for AWS services across regions.
"""

import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple, cast

import boto3
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    NoCredentialsError,
)
from rich.console import Console

# Import cache functions
from .cache import cache_result, get_cached_result

# Import logging (using simplified logging)
from .logging import get_logger

# Module-level logger
logger = get_logger()

# Import service scanners inside functions to avoid circular imports
# from services import (...)


console = Console()

# Supported services for traditional scanning
SUPPORTED_SERVICES = ["ec2", "s3", "ecs", "elb", "vpc", "autoscaling"]


def scan_all_services_with_tags(
    session: boto3.Session,
    region: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
    use_cache: bool = True,
) -> Tuple[str, Dict[str, Any], float]:
    """
    Scan ALL AWS services using Resource Groups Tagging API.

    This function provides service-agnostic resource discovery across ALL AWS services
    that support tagging, not just the traditional 6 services (EC2, VPC, S3, etc.).

    Returns resources in the same format as scan_region for compatibility.
    """
    from .resource_groups_utils import scan_all_tagged_resources

    start_time = time.time()

    logger.debug("Starting all-services scan in region %s", region)
    logger.log_aws_operation(
        "resource-groups",
        "scan_all_tagged_resources",
        region,
        tag_key=tag_key,
        tag_value=tag_value,
    )

    # Check cache first
    if use_cache:
        logger.log_cache_operation(
            "check", f"{region}:all_services:{tag_key}:{tag_value}"
        )
        cached_result = get_cached_result(region, "all_services", tag_key, tag_value)
        if cached_result is not None:
            logger.log_cache_operation(
                "hit",
                f"{region}:all_services",
                hit=True,
                resource_count=sum(
                    len(v) if isinstance(v, list) else 1 for v in cached_result.values()
                ),
            )
            scan_duration = time.time() - start_time
            return region, cached_result, scan_duration

    try:
        with logger.timer(f"All-services scan in {region}"):
            # Use service-agnostic Resource Groups API scan
            results = scan_all_tagged_resources(session, region, tag_key, tag_value)

        scan_duration = time.time() - start_time
        resource_count = sum(
            len(v) if isinstance(v, list) else 1 for v in results.values()
        )

        # Cache the results
        if use_cache and results:
            logger.log_cache_operation(
                "store", f"{region}:all_services", resource_count=resource_count
            )
            cache_result(region, "all_services", results, tag_key, tag_value)

        logger.log_scan_progress("all-services", region, resource_count, scan_duration)

        if not results:
            logger.info("No tagged resources found in region %s", region)

        return region, results, scan_duration

    except (ClientError, EndpointConnectionError, ConnectTimeoutError) as e:
        logger.error("Failed cross-service scan in region %s: %s", region, str(e))
        logger.log_error_context(
            e,
            {
                "region": region,
                "operation": "all_services_scan",
                "tag_key": tag_key,
                "tag_value": tag_value,
            },
        )
        return region, {}, time.time() - start_time


def retry_with_backoff(func: Any, max_retries: int = 3, base_delay: float = 1) -> Any:
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
                    logger.warning(
                        "Retrying in %.1fs due to %s (attempt %d/%d)",
                        delay,
                        error_code,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(delay)
                    continue
            raise e
        except (EndpointConnectionError, ConnectTimeoutError) as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "Retrying connection in %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    max_retries,
                )
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
            # Cache message now displayed upfront, just return silently
            return cached_result

    def _do_scan() -> Dict[str, Any]:
        # Import service scanners here to avoid circular imports
        from services import (
            scan_autoscaling,
            scan_ec2,
            scan_ecs,
            scan_elb,
            scan_s3,
            scan_vpc,
        )

        if service == "ec2":
            return scan_ec2(
                session, region
            )  # No tag filtering in service-specific scan
        elif service == "s3":
            return scan_s3(session, region)  # No tag filtering in service-specific scan
        elif service == "ecs":
            return scan_ecs(
                session, region
            )  # No tag filtering in service-specific scan
        elif service == "elb":
            return scan_elb(
                session, region
            )  # No tag filtering in service-specific scan
        elif service == "vpc":
            return scan_vpc(
                session, region
            )  # No tag filtering in service-specific scan
        elif service == "autoscaling":
            # Auto Scaling supports tag filtering even in service-specific scan
            # because resourcegroupapi does not support ASG
            return scan_autoscaling(session, region, tag_key, tag_value)
        else:
            logger.warning("Service scan for '%s' not implemented yet", service)
            return {}

    try:
        result = retry_with_backoff(_do_scan)

        # Cache the result
        if use_cache and result:
            cache_result(region, service, result, tag_key, tag_value)

        return cast(Dict[str, Any], result)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(
            "AWS API Error for %s in %s: %s - %s", service, region, error_code, str(e)
        )
        return {}
    except EndpointConnectionError as e:
        logger.error("Connection Error for %s in %s: %s", service, region, str(e))
        return {}
    except NoCredentialsError as e:
        logger.error("Credentials Error for %s in %s: %s", service, region, str(e))
        return {}
    except (OSError, RuntimeError, ValueError) as e:
        logger.error("Unexpected error scanning %s in %s: %s", service, region, str(e))
        return {}


def scan_region(
    session: boto3.Session,
    region: str,
    services: List[str],
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
    service_workers: int = 4,
    use_cache: bool = True,
    progress_callback: Optional[Any] = None,
    shutdown_event: Optional[Any] = None,
) -> Tuple[str, Dict[str, Any], float]:
    """Scan all services in a single region with parallel service scanning."""
    start_time = time.time()
    region_results = {}

    logger.debug("Starting region scan for %s with %d services", region, len(services))
    logger.debug(
        "Service configuration: workers=%d, cache=%s", service_workers, use_cache
    )

    # Limit workers to reasonable bounds
    max_service_workers = min(len(services), max(1, min(service_workers, 10)))

    if max_service_workers != service_workers:
        logger.debug(
            "Adjusted service workers from %d to %d for region %s",
            service_workers,
            max_service_workers,
            region,
        )

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
            # Check for shutdown request before processing each service
            if shutdown_event and shutdown_event.is_set():
                logger.warning("Cancelling remaining services in region %s", region)
                # Cancel remaining futures
                for pending_future in future_to_service:
                    if not pending_future.done():
                        pending_future.cancel()
                break

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
            except (
                ClientError,
                EndpointConnectionError,
                ConnectTimeoutError,
                NoCredentialsError,
            ) as e:
                logger.error("Error scanning %s in %s: %s", service, region, str(e))
                logger.log_error_context(
                    e,
                    {"service": service, "region": region, "operation": "service_scan"},
                )
                service_results_summary[service] = 0

            # Update progress if callback provided
            completed_services += 1
            if progress_callback:
                progress_callback(completed_services, total_services, service, region)

    # Calculate and display region scan time
    end_time = time.time()
    scan_duration = end_time - start_time

    # Log region completion
    total_resources = sum(service_results_summary.values())
    logger.log_scan_progress("region", region, total_resources, scan_duration)

    if logger.is_debug_enabled():
        logger.debug("Region %s service breakdown:", region)
        for service, count in service_results_summary.items():
            logger.debug("  • %s: %d resources", service, count)

    # Only show region completion in debug mode to avoid interfering with progress
    if logger.is_debug_enabled():
        logger.debug("Region %s scan completed in %.1fs", region, scan_duration)

    return region, region_results, scan_duration
