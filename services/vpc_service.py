"""
VPC Service Scanner
------------------

Scans VPC resources: VPCs, subnets, NAT gateways, internet gateways,
route tables, DHCP options, VPC peering connections, and VPC endpoints.
Tag-based filtering is handled by the Resource Groups API at the main
scanner level.

Fully declarative: every resource type is one paginated describe call,
so the whole scan is a Describe spec executed by the shared engine.
? Documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html
"""

from typing import Any

from aws_scanner_lib.clients import get_scan_client
from aws_scanner_lib.engine import Describe, ScanResult, scan_keyed
from aws_scanner_lib.records import Resource

VPC_SPECS: dict[str, Describe] = {
    "vpcs": Describe("describe_vpcs", "Vpcs"),
    "subnets": Describe("describe_subnets", "Subnets"),
    "internet_gateways": Describe("describe_internet_gateways", "InternetGateways"),
    "route_tables": Describe("describe_route_tables", "RouteTables"),
    "nat_gateways": Describe("describe_nat_gateways", "NatGateways"),
    "dhcp_options": Describe("describe_dhcp_options", "DhcpOptions"),
    "vpc_peering_connections": Describe(
        "describe_vpc_peering_connections", "VpcPeeringConnections"
    ),
    "vpc_endpoints": Describe("describe_vpc_endpoints", "VpcEndpoints"),
}


def scan_vpc(session: Any, region: str) -> ScanResult:
    """Scan all VPC resources in the region (no tag filtering)."""
    client = get_scan_client(session, "ec2", region)
    return scan_keyed(client, VPC_SPECS, service="vpc", region=region, max_workers=4)


def process_vpc_output(
    service_data: dict[str, Any],
    region: str,
    flattened_resources: list[Resource],
) -> None:
    """Process VPC scan results for output formatting."""
    # VPCs
    for vpc in service_data.get("vpcs", []):
        vpc_id = vpc.get("VpcId", "N/A")
        cidr_block = vpc.get("CidrBlock", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=f"VPC-{cidr_block}",
                resource_type="vpc",
                resource_id=vpc_id,
                resource_arn="N/A",  # VPCs don't have ARNs in AWS API
            )
        )

    # Subnets
    for subnet in service_data.get("subnets", []):
        subnet_id = subnet.get("SubnetId", "N/A")
        cidr_block = subnet.get("CidrBlock", "N/A")
        # Use actual subnet ARN from API response
        subnet_arn = subnet.get("SubnetArn", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=f"Subnet-{cidr_block}",
                resource_type="vpc:subnet",
                resource_id=subnet_id,
                resource_arn=subnet_arn,  # Use actual ARN from describe_subnets API
            )
        )

    # NAT Gateways
    for nat_gw in service_data.get("nat_gateways", []):
        nat_gw_id = nat_gw.get("NatGatewayId", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=nat_gw_id,
                resource_type="vpc:nat_gateway",
                resource_id=nat_gw_id,
                resource_arn="N/A",  # NAT Gateways don't have ARNs in AWS API
            )
        )

    # Internet Gateways
    for igw in service_data.get("internet_gateways", []):
        igw_id = igw.get("InternetGatewayId", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=igw_id,
                resource_type="vpc:internet_gateway",
                resource_id=igw_id,
                resource_arn="N/A",  # Internet Gateways don't have ARNs in AWS API
            )
        )

    # Route Tables
    for rt in service_data.get("route_tables", []):
        rt_id = rt.get("RouteTableId", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=rt_id,
                resource_type="vpc:route_table",
                resource_id=rt_id,
                resource_arn="N/A",  # Route Tables don't have ARNs in AWS API
            )
        )

    # DHCP Options
    for dhcp in service_data.get("dhcp_options", []):
        dhcp_id = dhcp.get("DhcpOptionsId", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=dhcp_id,
                resource_type="vpc:dhcp_options",
                resource_id=dhcp_id,
                resource_arn="N/A",  # DHCP Options don't have ARNs in AWS API
            )
        )

    # VPC Peering Connections
    for peering in service_data.get("vpc_peering_connections", []):
        peering_id = peering.get("VpcPeeringConnectionId", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=peering_id,
                resource_type="vpc:peering_connection",
                resource_id=peering_id,
                resource_arn="N/A",  # VPC Peering Connections don't have ARNs in AWS API
            )
        )

    # VPC Endpoints
    for endpoint in service_data.get("vpc_endpoints", []):
        endpoint_id = endpoint.get("VpcEndpointId", "N/A")
        service_name = endpoint.get("ServiceName", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=f"{endpoint_id}-{service_name.split('.')[-1] if service_name != 'N/A' else 'unknown'}",
                resource_type="vpc:endpoint",
                resource_id=endpoint_id,
                resource_arn="N/A",  # VPC Endpoints don't have ARNs in AWS API
            )
        )
