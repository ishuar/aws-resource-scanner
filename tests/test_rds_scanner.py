"""
RDS scanner seam: services.rds_service against a fake AWS (moto).

Functional tests: create real-shaped RDS resources in moto, run the
scanner through its public interface (session, region), and pin the
result-key vocabulary, the resources found, and the raw fields the
future waste rules need (DBInstanceStatus, storage). The processor test
pins the flattened Resource vocabulary via .to_record().
"""

from typing import Any

from aws_scanner_lib.records import Resource
from services.rds_service import process_rds_output, scan_rds

REGION = "eu-central-1"


def _create_rds_resources(aws_session: Any) -> dict[str, str]:
    """Create one DB instance, one DB cluster, and one manual snapshot."""
    rds = aws_session.client("rds", region_name=REGION)
    instance_id = "app-db"
    rds.create_db_instance(
        DBInstanceIdentifier=instance_id,
        DBInstanceClass="db.t3.micro",
        Engine="postgres",
        MasterUsername="admin",
        MasterUserPassword="password123",
        AllocatedStorage=20,
    )
    cluster_id = "app-cluster"
    rds.create_db_cluster(
        DBClusterIdentifier=cluster_id,
        Engine="aurora-mysql",
        MasterUsername="admin",
        MasterUserPassword="password123",
    )
    snapshot_id = "app-db-manual-snap"
    rds.create_db_snapshot(
        DBSnapshotIdentifier=snapshot_id,
        DBInstanceIdentifier=instance_id,
    )
    return {
        "instance_id": instance_id,
        "cluster_id": cluster_id,
        "snapshot_id": snapshot_id,
    }


class TestScanRds:
    def test_result_keys_and_created_resources_are_found(
        self, aws_session: Any
    ) -> None:
        ids = _create_rds_resources(aws_session)

        result = scan_rds(aws_session, REGION)

        assert set(result) == {"db_instances", "db_clusters", "db_snapshots"}
        # Membership, not exact counts: creating an aurora cluster may
        # auto-create instances, and moto may include automated snapshots.
        assert ids["instance_id"] in [
            i["DBInstanceIdentifier"] for i in result["db_instances"]
        ]
        assert ids["cluster_id"] in [
            c["DBClusterIdentifier"] for c in result["db_clusters"]
        ]
        assert ids["snapshot_id"] in [
            s["DBSnapshotIdentifier"] for s in result["db_snapshots"]
        ]

    def test_raw_fields_for_waste_rules_are_present(self, aws_session: Any) -> None:
        # The future rds-stopped waste rule reads DBInstanceStatus and the
        # storage fields straight off the raw boto3 dicts — pin them here.
        ids = _create_rds_resources(aws_session)

        result = scan_rds(aws_session, REGION)

        instance = next(
            i
            for i in result["db_instances"]
            if i["DBInstanceIdentifier"] == ids["instance_id"]
        )
        assert "DBInstanceStatus" in instance
        assert instance["AllocatedStorage"] == 20

    def test_empty_region_returns_all_keys_with_empty_lists(
        self, aws_session: Any
    ) -> None:
        result = scan_rds(aws_session, REGION)
        assert result == {"db_instances": [], "db_clusters": [], "db_snapshots": []}


class TestProcessRdsOutput:
    def test_flattens_instances_clusters_and_snapshots(self) -> None:
        arn_prefix = f"arn:aws:rds:{REGION}:123456789012"
        service_data = {
            "db_instances": [
                {
                    "DBInstanceIdentifier": "app-db",
                    "DBInstanceArn": f"{arn_prefix}:db:app-db",
                    "DBInstanceStatus": "stopped",
                    "AllocatedStorage": 20,
                }
            ],
            "db_clusters": [
                {
                    "DBClusterIdentifier": "app-cluster",
                    "DBClusterArn": f"{arn_prefix}:cluster:app-cluster",
                }
            ],
            "db_snapshots": [
                {
                    "DBSnapshotIdentifier": "app-db-manual-snap",
                    "DBSnapshotArn": f"{arn_prefix}:snapshot:app-db-manual-snap",
                }
            ],
        }

        flattened: list[Resource] = []
        process_rds_output(service_data, REGION, flattened)

        assert [r.to_record() for r in flattened] == [
            {
                "region": REGION,
                "resource_name": "app-db",
                "resource_type": "rds:db_instance",
                "resource_id": "app-db",
                "resource_arn": f"{arn_prefix}:db:app-db",
            },
            {
                "region": REGION,
                "resource_name": "app-cluster",
                "resource_type": "rds:db_cluster",
                "resource_id": "app-cluster",
                "resource_arn": f"{arn_prefix}:cluster:app-cluster",
            },
            {
                "region": REGION,
                "resource_name": "app-db-manual-snap",
                "resource_type": "rds:db_snapshot",
                "resource_id": "app-db-manual-snap",
                "resource_arn": f"{arn_prefix}:snapshot:app-db-manual-snap",
            },
        ]

    def test_empty_service_data_appends_nothing(self) -> None:
        flattened: list[Resource] = []
        process_rds_output({}, REGION, flattened)
        assert flattened == []
