"""
RDS Service Scanner
-------------------

Scans RDS resources: DB instances, DB clusters, and DB snapshots.
Tag-based filtering is handled by the Resource Groups API at the main
scanner level.

Fully declarative: every resource type is one paginated describe call,
so the whole scan is a Describe spec executed by the shared engine.
Raw boto3 dicts are kept as values — the future waste rules (e.g.
rds-stopped) read DBInstanceStatus and the storage fields off them.
Documentation: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/rds.html
"""

from typing import Any

from aws_scanner_lib.clients import get_scan_client
from aws_scanner_lib.engine import Describe, ScanResult, scan_keyed
from aws_scanner_lib.records import Resource

RDS_SPECS: dict[str, Describe] = {
    "db_instances": Describe("describe_db_instances", "DBInstances"),
    "db_clusters": Describe("describe_db_clusters", "DBClusters"),
    "db_snapshots": Describe("describe_db_snapshots", "DBSnapshots"),
    "db_cluster_snapshots": Describe(
        "describe_db_cluster_snapshots", "DBClusterSnapshots"
    ),
}


def scan_rds(session: Any, region: str) -> ScanResult:
    """Scan all RDS resources in the region (no tag filtering)."""
    client = get_scan_client(session, "rds", region)
    return scan_keyed(client, RDS_SPECS, service="rds", region=region, max_workers=4)


def process_rds_output(
    service_data: dict[str, Any],
    region: str,
    flattened_resources: list[Resource],
) -> None:
    """Process RDS scan results for output formatting."""
    # DB Instances
    for instance in service_data.get("db_instances", []):
        instance_id = instance.get("DBInstanceIdentifier", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=instance_id,
                resource_type="rds:db_instance",
                resource_id=instance_id,
                resource_arn=instance.get("DBInstanceArn", "N/A"),
            )
        )

    # DB Clusters
    for cluster in service_data.get("db_clusters", []):
        cluster_id = cluster.get("DBClusterIdentifier", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=cluster_id,
                resource_type="rds:db_cluster",
                resource_id=cluster_id,
                resource_arn=cluster.get("DBClusterArn", "N/A"),
            )
        )

    # DB Cluster Snapshots (Aurora)
    for snapshot in service_data.get("db_cluster_snapshots", []):
        snapshot_id = snapshot.get("DBClusterSnapshotIdentifier", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=snapshot_id,
                resource_type="rds:db_cluster_snapshot",
                resource_id=snapshot_id,
                resource_arn=snapshot.get("DBClusterSnapshotArn", "N/A"),
            )
        )

    # DB Snapshots
    for snapshot in service_data.get("db_snapshots", []):
        snapshot_id = snapshot.get("DBSnapshotIdentifier", "N/A")

        flattened_resources.append(
            Resource(
                region=region,
                resource_name=snapshot_id,
                resource_type="rds:db_snapshot",
                resource_id=snapshot_id,
                resource_arn=snapshot.get("DBSnapshotArn", "N/A"),
            )
        )
