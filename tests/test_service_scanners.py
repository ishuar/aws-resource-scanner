"""
Scanner seams: services.*.scan_* against a fake AWS (moto).

Functional tests: create real-shaped resources in moto, run each scanner
through its public interface (session, region), and pin the result-key
vocabulary and the resources found. The spec-driven-scanner refactor
(candidate 3) must keep every one of these passing.
"""

from typing import Any

import pytest

from services.autoscaling_service import scan_autoscaling
from services.ec2_service import scan_ec2
from services.ecs_service import scan_ecs
from services.elb_service import scan_elb
from services.s3_service import scan_s3
from services.vpc_service import scan_vpc

REGION = "eu-central-1"


class TestScanEc2:
    def test_result_keys_and_created_resources_are_found(
        self, aws_session: Any
    ) -> None:
        ec2 = aws_session.client("ec2", region_name=REGION)
        ami_id = ec2.describe_images(Owners=["amazon"])["Images"][0]["ImageId"]
        instance_id = ec2.run_instances(ImageId=ami_id, MinCount=1, MaxCount=1)[
            "Instances"
        ][0]["InstanceId"]
        volume_id = ec2.create_volume(AvailabilityZone=f"{REGION}a", Size=8)["VolumeId"]
        snapshot_id = ec2.create_snapshot(VolumeId=volume_id)["SnapshotId"]
        image_id = ec2.create_image(InstanceId=instance_id, Name="golden")["ImageId"]

        result = scan_ec2(aws_session, REGION)

        assert set(result) == {
            "instances",
            "volumes",
            "security_groups",
            "amis",
            "snapshots",
        }
        assert instance_id in [i["InstanceId"] for i in result["instances"]]
        assert volume_id in [v["VolumeId"] for v in result["volumes"]]
        assert snapshot_id in [s["SnapshotId"] for s in result["snapshots"]]
        # Owners=["self"] — only images this account created.
        assert image_id in [a["ImageId"] for a in result["amis"]]
        assert ami_id not in [a["ImageId"] for a in result["amis"]]
        # The default security group always exists.
        assert "default" in [sg["GroupName"] for sg in result["security_groups"]]

    def test_empty_region_returns_all_keys_with_empty_lists(
        self, aws_session: Any
    ) -> None:
        result = scan_ec2(aws_session, REGION)
        assert result["instances"] == []
        assert result["volumes"] == []
        assert result["amis"] == []
        # No snapshots assertion: moto seeds public snapshots and does not
        # honour the OwnerIds=["self"] filter, so the list is never empty
        # under moto. Ownership filtering is covered by the created-resource
        # test above.


class TestScanS3:
    def test_only_buckets_in_the_target_region_are_returned(
        self, aws_session: Any
    ) -> None:
        s3 = aws_session.client("s3", region_name=REGION)
        s3.create_bucket(
            Bucket="in-region",
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )
        aws_session.client("s3", region_name="us-east-1").create_bucket(
            Bucket="other-region"
        )

        result = scan_s3(aws_session, REGION)

        assert [b["Name"] for b in result["buckets"]] == ["in-region"]

    def test_bucket_tags_are_injected_under_lowercase_tags_key(
        self, aws_session: Any
    ) -> None:
        s3 = aws_session.client("s3", region_name=REGION)
        s3.create_bucket(
            Bucket="tagged",
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )
        s3.put_bucket_tagging(
            Bucket="tagged",
            Tagging={"TagSet": [{"Key": "env", "Value": "prod"}]},
        )
        s3.create_bucket(
            Bucket="untagged",
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )

        buckets = {b["Name"]: b for b in scan_s3(aws_session, REGION)["buckets"]}

        assert buckets["tagged"]["tags"] == [{"Key": "env", "Value": "prod"}]
        # NoSuchTagSet degrades to an empty list, not an error.
        assert buckets["untagged"]["tags"] == []


class TestScanVpc:
    def test_result_keys_and_created_resources_are_found(
        self, aws_session: Any
    ) -> None:
        ec2 = aws_session.client("ec2", region_name=REGION)
        vpc_id = ec2.create_vpc(CidrBlock="10.1.0.0/16")["Vpc"]["VpcId"]
        subnet_id = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.1.1.0/24")["Subnet"][
            "SubnetId"
        ]
        igw_id = ec2.create_internet_gateway()["InternetGateway"]["InternetGatewayId"]

        result = scan_vpc(aws_session, REGION)

        assert set(result) == {
            "vpcs",
            "subnets",
            "internet_gateways",
            "route_tables",
            "nat_gateways",
            "dhcp_options",
            "vpc_peering_connections",
            "vpc_endpoints",
        }
        assert vpc_id in [v["VpcId"] for v in result["vpcs"]]
        assert subnet_id in [s["SubnetId"] for s in result["subnets"]]
        assert igw_id in [g["InternetGatewayId"] for g in result["internet_gateways"]]
        # Creating a VPC always creates a main route table.
        assert any(rt["VpcId"] == vpc_id for rt in result["route_tables"])


class TestScanElb:
    def _create_alb(self, aws_session: Any) -> Any:
        ec2 = aws_session.client("ec2", region_name=REGION)
        elbv2 = aws_session.client("elbv2", region_name=REGION)
        vpc_id = ec2.create_vpc(CidrBlock="10.2.0.0/16")["Vpc"]["VpcId"]
        subnet_a = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.2.1.0/24", AvailabilityZone=f"{REGION}a"
        )["Subnet"]["SubnetId"]
        subnet_b = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.2.2.0/24", AvailabilityZone=f"{REGION}b"
        )["Subnet"]["SubnetId"]
        lb_arn = elbv2.create_load_balancer(
            Name="my-alb",
            Subnets=[subnet_a, subnet_b],
            Tags=[{"Key": "env", "Value": "prod"}],
        )["LoadBalancers"][0]["LoadBalancerArn"]
        tg_arn = elbv2.create_target_group(
            Name="my-tg", Protocol="HTTP", Port=80, VpcId=vpc_id
        )["TargetGroups"][0]["TargetGroupArn"]
        elbv2.create_listener(
            LoadBalancerArn=lb_arn,
            Protocol="HTTP",
            Port=80,
            DefaultActions=[{"Type": "forward", "TargetGroupArn": tg_arn}],
        )
        return lb_arn

    def test_result_keys_and_created_resources_are_found(
        self, aws_session: Any
    ) -> None:
        lb_arn = self._create_alb(aws_session)

        result = scan_elb(aws_session, REGION)

        assert set(result) == {
            "load_balancers",
            "target_groups",
            "listeners",
            "listener_rules",
        }
        assert [lb["LoadBalancerArn"] for lb in result["load_balancers"]] == [lb_arn]
        assert result["load_balancers"][0]["Tags"] == [{"Key": "env", "Value": "prod"}]
        assert [tg["TargetGroupName"] for tg in result["target_groups"]] == ["my-tg"]
        assert len(result["listeners"]) == 1
        # The second (winning) listener pass annotates the LB name.
        assert result["listeners"][0]["LoadBalancerName"] == "my-alb"
        # Every listener has at least its default rule.
        assert len(result["listener_rules"]) >= 1
        assert result["listener_rules"][0]["LoadBalancerArn"] == lb_arn

    def test_empty_region_yields_empty_lists(self, aws_session: Any) -> None:
        result = scan_elb(aws_session, REGION)
        assert result["load_balancers"] == []
        assert result["listeners"] == []


class TestScanEcs:
    @pytest.fixture(autouse=True)
    def _moto_capacity_provider_shim(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # moto 5.2 crashes on describe_capacity_providers() without an
        # explicit name list (names is None → TypeError). Shim the fake so
        # the scanner's real no-args call works; the scanner code itself is
        # untouched.
        from moto.ecs.models import EC2ContainerServiceBackend

        original = EC2ContainerServiceBackend.describe_capacity_providers

        def patched(self: Any, names: Any, *args: Any, **kwargs: Any) -> Any:
            return original(self, names or [], *args, **kwargs)

        monkeypatch.setattr(
            EC2ContainerServiceBackend, "describe_capacity_providers", patched
        )

    def test_result_keys_and_created_resources_are_found(
        self, aws_session: Any
    ) -> None:
        ecs = aws_session.client("ecs", region_name=REGION)
        ecs.create_cluster(clusterName="prod")
        container_defs = [{"name": "app", "image": "app:latest", "memory": 128}]
        ecs.register_task_definition(family="api", containerDefinitions=container_defs)
        ecs.create_service(
            cluster="prod", serviceName="api-svc", taskDefinition="api", desiredCount=1
        )

        result = scan_ecs(aws_session, REGION)

        assert set(result) == {
            "clusters",
            "services",
            "task_definitions",
            "capacity_providers",
        }
        assert [c["clusterName"] for c in result["clusters"]] == ["prod"]
        services = {s["serviceName"]: s for s in result["services"]}
        assert services["api-svc"]["clusterName"] == "prod"
        assert [
            td["taskDefinitionArn"].split("/")[-1] for td in result["task_definitions"]
        ] == ["api:1"]

    def test_only_the_latest_two_task_definition_revisions_are_kept(
        self, aws_session: Any
    ) -> None:
        ecs = aws_session.client("ecs", region_name=REGION)
        ecs.create_cluster(clusterName="prod")
        container_defs = [{"name": "app", "image": "app:latest", "memory": 128}]
        for _ in range(4):
            ecs.register_task_definition(
                family="api", containerDefinitions=container_defs
            )

        result = scan_ecs(aws_session, REGION)

        revisions = sorted(
            td["taskDefinitionArn"].split("/")[-1] for td in result["task_definitions"]
        )
        # The scanner requests sort="DESC" to keep the latest two revisions.
        # moto ignores the sort parameter, so which two come back is not
        # asserted here — the cap of 2 per family is the pinned behaviour.
        assert len(revisions) == 2


class TestScanAutoscaling:
    def _create_asgs(self, aws_session: Any) -> None:
        ec2 = aws_session.client("ec2", region_name=REGION)
        autoscaling = aws_session.client("autoscaling", region_name=REGION)
        ec2.create_launch_template(
            LaunchTemplateName="web-lt",
            LaunchTemplateData={"ImageId": "ami-12345678", "InstanceType": "t3.micro"},
            TagSpecifications=[
                {
                    "ResourceType": "launch-template",
                    "Tags": [{"Key": "env", "Value": "prod"}],
                }
            ],
        )
        for name, tags in [
            ("prod-asg", [{"Key": "env", "Value": "prod"}]),
            ("dev-asg", [{"Key": "env", "Value": "dev"}]),
            ("untagged-asg", []),
        ]:
            autoscaling.create_auto_scaling_group(
                AutoScalingGroupName=name,
                MinSize=0,
                MaxSize=1,
                AvailabilityZones=[f"{REGION}a"],
                LaunchTemplate={"LaunchTemplateName": "web-lt"},
                Tags=[
                    {**t, "ResourceId": name, "ResourceType": "auto-scaling-group"}
                    for t in tags
                ],
            )

    def asg_names(self, result: Any) -> list:
        return sorted(a["AutoScalingGroupName"] for a in result["auto_scaling_groups"])

    def test_no_tags_returns_everything(self, aws_session: Any) -> None:
        self._create_asgs(aws_session)
        result = scan_autoscaling(aws_session, REGION)

        assert set(result) == {
            "auto_scaling_groups",
            "launch_configurations",
            "launch_templates",
        }
        assert self.asg_names(result) == ["dev-asg", "prod-asg", "untagged-asg"]
        assert [t["LaunchTemplateName"] for t in result["launch_templates"]] == [
            "web-lt"
        ]

    def test_key_and_value_filter_requires_an_exact_match(
        self, aws_session: Any
    ) -> None:
        self._create_asgs(aws_session)
        result = scan_autoscaling(aws_session, REGION, "env", "prod")
        assert self.asg_names(result) == ["prod-asg"]

    def test_key_only_filter_matches_any_value(self, aws_session: Any) -> None:
        self._create_asgs(aws_session)
        result = scan_autoscaling(aws_session, REGION, tag_key="env")
        assert self.asg_names(result) == ["dev-asg", "prod-asg"]

    def test_value_only_filter_matches_any_key(self, aws_session: Any) -> None:
        self._create_asgs(aws_session)
        result = scan_autoscaling(aws_session, REGION, tag_value="prod")
        assert self.asg_names(result) == ["prod-asg"]

    def test_no_match_returns_empty_lists(self, aws_session: Any) -> None:
        self._create_asgs(aws_session)
        result = scan_autoscaling(aws_session, REGION, "env", "does-not-exist")
        assert result["auto_scaling_groups"] == []
        assert result["launch_configurations"] == []
