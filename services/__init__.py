"""
AWS Services Package
-------------------

This package contains modules for scanning different AWS services.
Each service has its own module with a scan function and output processing.
"""

from .ec2_service import scan_ec2, process_ec2_output
from .s3_service import scan_s3, process_s3_output
from .ecs_service import scan_ecs, process_ecs_output
from .elb_service import scan_elb, process_elb_output
from .vpc_service import scan_vpc, process_vpc_output
from .autoscaling_service import scan_autoscaling, process_autoscaling_output

__all__ = [
    "scan_ec2",
    "process_ec2_output",
    "scan_s3",
    "process_s3_output",
    "scan_ecs",
    "process_ecs_output",
    "scan_elb",
    "process_elb_output",
    "scan_vpc",
    "process_vpc_output",
    "scan_autoscaling",
    "process_autoscaling_output",
]
