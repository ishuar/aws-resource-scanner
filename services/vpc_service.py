"""
VPC Service Scanner
------------------

Handles scanning of VPC resources including VPCs, subnets, NAT gateways, internet gateways,
route tables, DHCP options, VPC peering connections, and VPC endpoints.
"""

import botocore  # pyright: ignore[reportMissingImports]
from rich.console import Console  # pyright: ignore[reportMissingImports]

console = Console()


def scan_vpc(session, region, tag_key=None, tag_value=None):
    """Scan VPC resources in the specified region with optimized API filtering and pagination."""
    ec2_client = session.client("ec2", region_name=region)
    result = {}

    # Build AWS API filters for tag filtering
    filters = []
    if tag_key and tag_value:
        filters.append({"Name": f"tag:{tag_key}", "Values": [tag_value]})

    try:
        # VPCs with API-level filtering and pagination
        vpcs = []
        paginator = ec2_client.get_paginator("describe_vpcs")
        page_iterator = (
            paginator.paginate(Filters=filters) if filters else paginator.paginate()
        )

        for page in page_iterator:
            vpcs.extend(page["Vpcs"])

        # Subnets with API-level filtering and pagination
        subnets = []
        paginator = ec2_client.get_paginator("describe_subnets")
        page_iterator = (
            paginator.paginate(Filters=filters) if filters else paginator.paginate()
        )

        for page in page_iterator:
            subnets.extend(page["Subnets"])

        # NAT Gateways with pagination (tag filtering done client-side as API doesn't support it)
        nat_gateways = []
        paginator = ec2_client.get_paginator("describe_nat_gateways")
        page_iterator = paginator.paginate()

        for page in page_iterator:
            for nat_gw in page["NatGateways"]:
                # NAT Gateways use a different tag structure
                if not filters or any(
                    t.get("Key") == tag_key and t.get("Value") == tag_value
                    for t in nat_gw.get("Tags", [])
                ):
                    nat_gateways.append(nat_gw)

        # Internet Gateways with API-level filtering and pagination
        internet_gateways = []
        paginator = ec2_client.get_paginator("describe_internet_gateways")
        page_iterator = (
            paginator.paginate(Filters=filters) if filters else paginator.paginate()
        )

        for page in page_iterator:
            internet_gateways.extend(page["InternetGateways"])

        # Route Tables with API-level filtering and pagination
        route_tables = []
        paginator = ec2_client.get_paginator("describe_route_tables")
        page_iterator = (
            paginator.paginate(Filters=filters) if filters else paginator.paginate()
        )

        for page in page_iterator:
            route_tables.extend(page["RouteTables"])

        # DHCP Options with pagination (no API-level tag filtering)
        dhcp_options = []
        try:
            paginator = ec2_client.get_paginator("describe_dhcp_options")
            page_iterator = paginator.paginate()

            for page in page_iterator:
                for dhcp_option in page["DhcpOptions"]:
                    if not filters or any(
                        t.get("Key") == tag_key and t.get("Value") == tag_value
                        for t in dhcp_option.get("Tags", [])
                    ):
                        dhcp_options.append(dhcp_option)
        except Exception:
            # Fallback to non-paginated call
            dhcp_options_response = ec2_client.describe_dhcp_options()
            for dhcp_option in dhcp_options_response["DhcpOptions"]:
                if not filters or any(
                    t.get("Key") == tag_key and t.get("Value") == tag_value
                    for t in dhcp_option.get("Tags", [])
                ):
                    dhcp_options.append(dhcp_option)

        # VPC Peering Connections with pagination (client-side filtering)
        vpc_peering_connections = []
        try:
            paginator = ec2_client.get_paginator("describe_vpc_peering_connections")
            page_iterator = paginator.paginate()

            for page in page_iterator:
                for peering_conn in page["VpcPeeringConnections"]:
                    if not filters or any(
                        t.get("Key") == tag_key and t.get("Value") == tag_value
                        for t in peering_conn.get("Tags", [])
                    ):
                        vpc_peering_connections.append(peering_conn)
        except Exception:
            # Fallback to non-paginated call
            peering_response = ec2_client.describe_vpc_peering_connections()
            for peering_conn in peering_response["VpcPeeringConnections"]:
                if not filters or any(
                    t.get("Key") == tag_key and t.get("Value") == tag_value
                    for t in peering_conn.get("Tags", [])
                ):
                    vpc_peering_connections.append(peering_conn)

        # VPC Endpoints with pagination (client-side filtering)
        vpc_endpoints = []
        try:
            paginator = ec2_client.get_paginator("describe_vpc_endpoints")
            page_iterator = paginator.paginate()

            for page in page_iterator:
                for endpoint in page["VpcEndpoints"]:
                    if not filters or any(
                        t.get("Key") == tag_key and t.get("Value") == tag_value
                        for t in endpoint.get("Tags", [])
                    ):
                        vpc_endpoints.append(endpoint)
        except Exception:
            # Fallback to non-paginated call
            endpoints_response = ec2_client.describe_vpc_endpoints()
            for endpoint in endpoints_response["VpcEndpoints"]:
                if not filters or any(
                    t.get("Key") == tag_key and t.get("Value") == tag_value
                    for t in endpoint.get("Tags", [])
                ):
                    vpc_endpoints.append(endpoint)

        result["vpcs"] = vpcs
        result["subnets"] = subnets
        result["nat_gateways"] = nat_gateways
        result["internet_gateways"] = internet_gateways
        result["route_tables"] = route_tables
        result["dhcp_options"] = dhcp_options
        result["vpc_peering_connections"] = vpc_peering_connections
        result["vpc_endpoints"] = vpc_endpoints

        # Store all results
        result["vpcs"] = vpcs
        result["subnets"] = subnets
        result["nat_gateways"] = nat_gateways
        result["internet_gateways"] = internet_gateways
        result["route_tables"] = route_tables
        result["dhcp_options"] = dhcp_options
        result["peering_connections"] = vpc_peering_connections
        result["endpoints"] = vpc_endpoints

    except botocore.exceptions.BotoCoreError as e:
        console.print(f"[red]VPC scan failed: {e}[/red]")
    return result


def process_vpc_output(service_data, region, flattened_resources):
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
    for peering in service_data.get("peering_connections", []):
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
    for endpoint in service_data.get("endpoints", []):
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
