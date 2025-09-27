"""
VPC Service Scanner
------------------

Handles scanning of VPC resources including VPCs, subnets, NAT gateways, internet gateways,
route tables, DHCP options, VPC peering connections, and VPC endpoints.
Prioritizes Resource Groups Tagging API for efficient server-side filtering when tags are available.
? Documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html

"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from botocore.exceptions import BotoCoreError, ClientError

from aws_scanner_lib.logging import get_logger, get_output_console

# Resource Groups API utilities removed - service-agnostic approach handled at main scanner level

# Service logger
logger = get_logger("vpc_service")

output_console = get_output_console() # VPC operations can be parallelized for better performance
VPC_MAX_WORKERS = 4  # Parallel workers for different resource types


def _scan_vpcs_parallel(
    ec2_client: Any, filters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Scan VPCs in parallel."""
    vpcs = []
    try:
        response = (
            ec2_client.describe_vpcs(Filters=filters)
            if filters
            else ec2_client.describe_vpcs()
        )
        vpcs.extend(response["Vpcs"])
    except (ClientError, BotoCoreError):
        pass
    return vpcs


def _scan_subnets_parallel(
    ec2_client: Any, filters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Scan subnets in parallel."""
    subnets = []
    try:
        response = (
            ec2_client.describe_subnets(Filters=filters)
            if filters
            else ec2_client.describe_subnets()
        )
        subnets.extend(response["Subnets"])
    except (ClientError, BotoCoreError):
        pass
    return subnets


def _scan_nat_gateways_parallel(
    ec2_client: Any, filters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Scan NAT gateways in parallel."""
    nat_gateways = []
    try:
        response = (
            ec2_client.describe_nat_gateways(Filters=filters)
            if filters
            else ec2_client.describe_nat_gateways()
        )
        nat_gateways.extend(response["NatGateways"])
    except (ClientError, BotoCoreError):
        pass
    return nat_gateways


def _scan_internet_gateways_parallel(
    ec2_client: Any, filters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Scan internet gateways in parallel."""
    igws = []
    try:
        response = (
            ec2_client.describe_internet_gateways(Filters=filters)
            if filters
            else ec2_client.describe_internet_gateways()
        )
        igws.extend(response["InternetGateways"])
    except (ClientError, BotoCoreError):
        pass
    return igws


def _scan_route_tables_parallel(
    ec2_client: Any, filters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Scan route tables in parallel."""
    route_tables = []
    try:
        response = (
            ec2_client.describe_route_tables(Filters=filters)
            if filters
            else ec2_client.describe_route_tables()
        )
        route_tables.extend(response["RouteTables"])
    except (ClientError, BotoCoreError):
        pass
    return route_tables


def _scan_dhcp_options_parallel(ec2_client: Any) -> List[Dict[str, Any]]:
    """Scan DHCP options without tag filtering."""
    dhcp_options = []
    try:
        response = ec2_client.describe_dhcp_options()
        dhcp_options.extend(response["DhcpOptions"])
    except (ClientError, BotoCoreError):
        pass
    return dhcp_options


def scan_vpc(
    session: Any,
    region: str,
) -> Dict[str, Any]:
    """
    Scan all VPC resources using describe APIs without tag filtering.

    Tag-based filtering is handled by the Resource Groups API at the main scanner level.
    """
    with logger.timer(f"vpc_scan_{region}"):
        logger.debug("Starting VPC resource scan in region %s", region)

        # Show progress only in debug mode to avoid interfering with progress bars
        if logger.is_debug_enabled():
            output_console.print(f"[blue]Scanning VPC resources in {region}[/blue]")

        result = {}
        ec2_client = session.client("ec2", region_name=region)

    try:
        # No tag filtering - use traditional approach with API-level filters
        filters: List[Dict[str, Any]] = []

        # Use ThreadPoolExecutor to parallelize VPC resource scanning
        with ThreadPoolExecutor(max_workers=VPC_MAX_WORKERS) as executor:
            # Submit core resource tasks that support API-level filtering
            vpcs_future = executor.submit(_scan_vpcs_parallel, ec2_client, filters)
            subnets_future = executor.submit(
                _scan_subnets_parallel, ec2_client, filters
            )
            igws_future = executor.submit(
                _scan_internet_gateways_parallel, ec2_client, filters
            )
            route_tables_future = executor.submit(
                _scan_route_tables_parallel, ec2_client, filters
            )
            # Submit tasks that need client-side filtering
            nat_gateways_future = executor.submit(
                _scan_nat_gateways_parallel, ec2_client, []
            )
            dhcp_options_future = executor.submit(
                _scan_dhcp_options_parallel, ec2_client
            )

        # Collect results with error handling (works for both Resource Groups API and traditional approaches)
        try:
            result["vpcs"] = vpcs_future.result()
        except (ClientError, BotoCoreError) as e:
            logger.warning("Failed to scan VPCs in region %s: %s", region, str(e))
            result["vpcs"] = []

        try:
            result["subnets"] = subnets_future.result()
        except (ClientError, BotoCoreError) as e:
            logger.warning("Failed to scan subnets in region %s: %s", region, str(e))
            result["subnets"] = []

        try:
            result["internet_gateways"] = igws_future.result()
        except (ClientError, BotoCoreError) as e:
            logger.warning("Failed to scan internet gateways in region %s: %s", region, str(e))
            result["internet_gateways"] = []

        try:
            result["route_tables"] = route_tables_future.result()
        except (ClientError, BotoCoreError) as e:
            logger.warning("Failed to scan route tables in region %s: %s", region, str(e))
            result["route_tables"] = []

        try:
            result["nat_gateways"] = nat_gateways_future.result()
        except (ClientError, BotoCoreError) as e:
            logger.warning("Failed to scan NAT gateways in region %s: %s", region, str(e))
            result["nat_gateways"] = []

        try:
            result["dhcp_options"] = dhcp_options_future.result()
        except (ClientError, BotoCoreError) as e:
            logger.warning("Failed to scan DHCP options in region %s: %s", region, str(e))
            result["dhcp_options"] = []

        # Handle remaining resources sequentially (lower priority/frequency)
        result["vpc_peering_connections"] = []
        result["vpc_endpoints"] = []

        # VPC Peering Connections (no tag filtering)
        try:
            paginator = ec2_client.get_paginator("describe_vpc_peering_connections")
            for page in paginator.paginate():
                result["vpc_peering_connections"].extend(page["VpcPeeringConnections"])
        except (ClientError, BotoCoreError):
            pass

        # VPC Endpoints (no tag filtering)
        try:
            paginator = ec2_client.get_paginator("describe_vpc_endpoints")
            for page in paginator.paginate():
                result["vpc_endpoints"].extend(page["VpcEndpoints"])
        except (ClientError, BotoCoreError):
            pass

    except BotoCoreError as e:
        logger.error("VPC scan failed in region %s: %s", region, str(e))

    # Log completion with resource count
    total_resources = sum(len(result.get(key, [])) for key in result.keys())
    logger.info("VPC scan completed in region %s: %d total resources", region, total_resources)

    # Debug-level details about each resource type
    for resource_type, resources in result.items():
        if resources:
            logger.debug("VPC %s in %s: %d resources", resource_type, region, len(resources))

    return result


def process_vpc_output(
    service_data: Dict[str, Any], region: str, flattened_resources: List[Dict[str, Any]]
) -> None:
    """Process VPC scan results for output formatting."""
    # VPCs
    for vpc in service_data.get("vpcs", []):
        vpc_id = vpc.get("VpcId", "N/A")
        cidr_block = vpc.get("CidrBlock", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": f"VPC-{cidr_block}",
                "resource_type": "vpc",
                "resource_id": vpc_id,
                "resource_arn": "N/A",  # VPCs don't have ARNs in AWS API
            }
        )

    # Subnets
    for subnet in service_data.get("subnets", []):
        subnet_id = subnet.get("SubnetId", "N/A")
        cidr_block = subnet.get("CidrBlock", "N/A")
        # Use actual subnet ARN from API response
        subnet_arn = subnet.get("SubnetArn", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": f"Subnet-{cidr_block}",
                "resource_type": "vpc:subnet",
                "resource_id": subnet_id,
                "resource_arn": subnet_arn,  # Use actual ARN from describe_subnets API
            }
        )

    # NAT Gateways
    for nat_gw in service_data.get("nat_gateways", []):
        nat_gw_id = nat_gw.get("NatGatewayId", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": nat_gw_id,
                "resource_type": "vpc:nat_gateway",
                "resource_id": nat_gw_id,
                "resource_arn": "N/A",  # NAT Gateways don't have ARNs in AWS API
            }
        )

    # Internet Gateways
    for igw in service_data.get("internet_gateways", []):
        igw_id = igw.get("InternetGatewayId", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": igw_id,
                "resource_type": "vpc:internet_gateway",
                "resource_id": igw_id,
                "resource_arn": "N/A",  # Internet Gateways don't have ARNs in AWS API
            }
        )

    # Route Tables
    for rt in service_data.get("route_tables", []):
        rt_id = rt.get("RouteTableId", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": rt_id,
                "resource_type": "vpc:route_table",
                "resource_id": rt_id,
                "resource_arn": "N/A",  # Route Tables don't have ARNs in AWS API
            }
        )

    # DHCP Options
    for dhcp in service_data.get("dhcp_options", []):
        dhcp_id = dhcp.get("DhcpOptionsId", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": dhcp_id,
                "resource_type": "vpc:dhcp_options",
                "resource_id": dhcp_id,
                "resource_arn": "N/A",  # DHCP Options don't have ARNs in AWS API
            }
        )

    # VPC Peering Connections
    for peering in service_data.get("vpc_peering_connections", []):
        peering_id = peering.get("VpcPeeringConnectionId", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": peering_id,
                "resource_type": "vpc:peering_connection",
                "resource_id": peering_id,
                "resource_arn": "N/A",  # VPC Peering Connections don't have ARNs in AWS API
            }
        )

    # VPC Endpoints
    for endpoint in service_data.get("vpc_endpoints", []):
        endpoint_id = endpoint.get("VpcEndpointId", "N/A")
        service_name = endpoint.get("ServiceName", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": f"{endpoint_id}-{service_name.split('.')[-1] if service_name != 'N/A' else 'unknown'}",
                "resource_type": "vpc:endpoint",
                "resource_id": endpoint_id,
                "resource_arn": "N/A",  # VPC Endpoints don't have ARNs in AWS API
            }
        )
