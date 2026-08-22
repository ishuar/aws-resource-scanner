"""
The scan-record contract.

``Resource`` is the one definition of the flattened record every output
processor produces and every output format (table, markdown, JSON)
consumes. Producers construct it — so a malformed record fails at
construction, in the producing module, instead of at report time in a
user's terminal.

``resource_name`` is optional: some producers genuinely have no friendly
name to offer. Serialization omits it entirely when absent, and keeps
the historical key order, so JSON output is byte-identical with the
hand-built dicts this type replaces.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Resource:
    """One discovered AWS resource in the unified output shape."""

    region: str
    resource_type: str  # unified "service:type" format, e.g. "ec2:instance"
    resource_id: str
    resource_arn: str
    resource_name: str | None = None

    @property
    def service(self) -> str:
        """The AWS service prefix of resource_type ("ec2:instance" -> "ec2").

        Bare legacy types without a colon (e.g. "vpc") are their own service.
        """
        return self.resource_type.split(":", 1)[0]

    def to_record(self) -> dict[str, Any]:
        """Serialize to the legacy record dict (stable key order)."""
        record: dict[str, Any] = {"region": self.region}
        if self.resource_name is not None:
            record["resource_name"] = self.resource_name
        record["resource_type"] = self.resource_type
        record["resource_id"] = self.resource_id
        record["resource_arn"] = self.resource_arn
        return record
