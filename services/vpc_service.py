"""
VPC Service Scanner
------------------

Handles scanning of VPC resources including VPCs, subnets, NAT gateways, internet gateways,
route tables, DHCP options, VPC peering connections, and VPC endpoints.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from botocore.exceptions import BotoCoreError, ClientError
from rich.console import Console  # pyright: ignore[reportMissingImports]

console = Console()

# VPC operations can be parallelized for better performance
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


def _scan_dhcp_options_parallel(
    ec2_client: Any, tag_key: Optional[str], tag_value: Optional[str]
) -> List[Dict[str, Any]]:
    """Scan DHCP options in parallel with client-side filtering."""
    dhcp_options = []
    try:
        response = ec2_client.describe_dhcp_options()
        for dhcp_option in response["DhcpOptions"]:
            if (
                not tag_key
                or not tag_value
                or any(
                    t.get("Key") == tag_key and t.get("Value") == tag_value
                    for t in dhcp_option.get("Tags", [])
                )
            ):
                dhcp_options.append(dhcp_option)
    except (ClientError, BotoCoreError):
        pass
    return dhcp_options


def scan_vpc(
    session: Any,
    region: str,
    tag_key: Optional[str] = None,
    tag_value: Optional[str] = None,
) -> Dict[str, Any]:
    """Scan VPC resources in the specified region using parallel processing."""
    ec2_client = session.client("ec2", region_name=region)
    result = {}

    # Build AWS API filters for tag filtering
    filters = []
    if tag_key and tag_value:
        filters.append({"Name": f"tag:{tag_key}", "Values": [tag_value]})

    try:
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
                _scan_dhcp_options_parallel, ec2_client, tag_key, tag_value
            )

            # Collect results with error handling
            try:
                result["vpcs"] = vpcs_future.result()
            except (ClientError, BotoCoreError) as e:
                console.print(
                    f"[yellow]Warning: Failed to scan VPCs in {region}: {str(e)}[/yellow]"
                )
                result["vpcs"] = []

            try:
                result["subnets"] = subnets_future.result()
            except (ClientError, BotoCoreError) as e:
                console.print(
                    f"[yellow]Warning: Failed to scan subnets in {region}: {str(e)}[/yellow]"
                )
                result["subnets"] = []

            try:
                result["internet_gateways"] = igws_future.result()
            except (ClientError, BotoCoreError) as e:
                console.print(
                    f"[yellow]Warning: Failed to scan internet gateways in {region}: {str(e)}[/yellow]"
                )
                result["internet_gateways"] = []

            try:
                result["route_tables"] = route_tables_future.result()
            except (ClientError, BotoCoreError) as e:
                console.print(
                    f"[yellow]Warning: Failed to scan route tables in {region}: {str(e)}[/yellow]"
                )
                result["route_tables"] = []

            try:
                # Filter NAT gateways client-side for tags if needed
                nat_gateways = nat_gateways_future.result()
                if tag_key and tag_value:
                    filtered_nat_gateways = []
                    for nat_gw in nat_gateways:
                        if any(
                            t.get("Key") == tag_key and t.get("Value") == tag_value
                            for t in nat_gw.get("Tags", [])
                        ):
                            filtered_nat_gateways.append(nat_gw)
                    result["nat_gateways"] = filtered_nat_gateways
                else:
                    result["nat_gateways"] = nat_gateways
            except (ClientError, BotoCoreError) as e:
                console.print(
                    f"[yellow]Warning: Failed to scan NAT gateways in {region}: {str(e)}[/yellow]"
                )
                result["nat_gateways"] = []

            try:
                result["dhcp_options"] = dhcp_options_future.result()
            except (ClientError, BotoCoreError) as e:
                console.print(
                    f"[yellow]Warning: Failed to scan DHCP options in {region}: {str(e)}[/yellow]"
                )
                result["dhcp_options"] = []

        # Handle remaining resources sequentially (lower priority/frequency)
        result["vpc_peering_connections"] = []
        result["vpc_endpoints"] = []

        # VPC Peering Connections (client-side filtering)
        try:
            paginator = ec2_client.get_paginator("describe_vpc_peering_connections")
            for page in paginator.paginate():
                for peering_conn in page["VpcPeeringConnections"]:
                    if (
                        not tag_key
                        or not tag_value
                        or any(
                            t.get("Key") == tag_key and t.get("Value") == tag_value
                            for t in peering_conn.get("Tags", [])
                        )
                    ):
                        result["vpc_peering_connections"].append(peering_conn)
        except (ClientError, BotoCoreError):
            pass

        # VPC Endpoints (client-side filtering)
        try:
            paginator = ec2_client.get_paginator("describe_vpc_endpoints")
            for page in paginator.paginate():
                for endpoint in page["VpcEndpoints"]:
                    if (
                        not tag_key
                        or not tag_value
                        or any(
                            t.get("Key") == tag_key and t.get("Value") == tag_value
                            for t in endpoint.get("Tags", [])
                        )
                    ):
                        result["vpc_endpoints"].append(endpoint)
        except (ClientError, BotoCoreError):
            pass

    except BotoCoreError as e:
        console.print(f"[red]VPC scan failed: {e}[/red]")

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
                "resource_family": "vpc",
                "resource_type": "vpc",
                "resource_id": vpc_id,
                "resource_arn": f"arn:aws:ec2:{region}:*:vpc/{vpc_id}",
            }
        )

    # Subnets
    for subnet in service_data.get("subnets", []):
        subnet_id = subnet.get("SubnetId", "N/A")
        cidr_block = subnet.get("CidrBlock", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": f"Subnet-{cidr_block}",
                "resource_family": "vpc",
                "resource_type": "subnet",
                "resource_id": subnet_id,
                "resource_arn": f"arn:aws:ec2:{region}:*:subnet/{subnet_id}",
            }
        )

    # NAT Gateways
    for nat_gw in service_data.get("nat_gateways", []):
        nat_gw_id = nat_gw.get("NatGatewayId", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": nat_gw_id,
                "resource_family": "vpc",
                "resource_type": "nat_gateway",
                "resource_id": nat_gw_id,
                "resource_arn": f"arn:aws:ec2:{region}:*:nat-gateway/{nat_gw_id}",
            }
        )

    # Internet Gateways
    for igw in service_data.get("internet_gateways", []):
        igw_id = igw.get("InternetGatewayId", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": igw_id,
                "resource_family": "vpc",
                "resource_type": "internet_gateway",
                "resource_id": igw_id,
                "resource_arn": f"arn:aws:ec2:{region}:*:internet-gateway/{igw_id}",
            }
        )

    # Route Tables
    for rt in service_data.get("route_tables", []):
        rt_id = rt.get("RouteTableId", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": rt_id,
                "resource_family": "vpc",
                "resource_type": "route_table",
                "resource_id": rt_id,
                "resource_arn": f"arn:aws:ec2:{region}:*:route-table/{rt_id}",
            }
        )

    # DHCP Options
    for dhcp in service_data.get("dhcp_options", []):
        dhcp_id = dhcp.get("DhcpOptionsId", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": dhcp_id,
                "resource_family": "vpc",
                "resource_type": "dhcp_options",
                "resource_id": dhcp_id,
                "resource_arn": f"arn:aws:ec2:{region}:*:dhcp-options/{dhcp_id}",
            }
        )

    # VPC Peering Connections
    for peering in service_data.get("vpc_peering_connections", []):
        peering_id = peering.get("VpcPeeringConnectionId", "N/A")

        flattened_resources.append(
            {
                "region": region,
                "resource_name": peering_id,
                "resource_family": "vpc",
                "resource_type": "peering_connection",
                "resource_id": peering_id,
                "resource_arn": f"arn:aws:ec2:{region}:*:vpc-peering-connection/{peering_id}",
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
                "resource_family": "vpc",
                "resource_type": "endpoint",
                "resource_id": endpoint_id,
                "resource_arn": f"arn:aws:ec2:{region}:*:vpc-endpoint/{endpoint_id}",
            }
        )
