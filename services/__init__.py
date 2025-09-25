"""
AWS Services Package
-------------------

This package contains modules for scanning different AWS services.
Each service has its own module with a scan function and output processing.
"""

from .autoscaling_service import process_autoscaling_output, scan_autoscaling
from .ec2_service import process_ec2_output, scan_ec2
from .ecs_service import process_ecs_output, scan_ecs
from .elb_service import process_elb_output, scan_elb
from .s3_service import process_s3_output, scan_s3
from .vpc_service import process_vpc_output, scan_vpc

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
