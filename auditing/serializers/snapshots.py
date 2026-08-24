from rest_framework import serializers
from access.serializers.snapshots import AccessUserSnapshotSerializer
from organizations.serializers.snapshots import BranchSnapshotSerializer, CompanySnapshotSerializer
from ..models import AuditEvent

# Define your auditing snapshot serializers here.

class AuditEventSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Audit Event Snapshot Serializer

        Description:
        - Provide a compact read-only representation of an audit event.

        Notes:
        - Audit records are immutable.
        - Sensitive request or authentication information is never exposed.
    """

    company = CompanySnapshotSerializer(read_only=True)
    branch = BranchSnapshotSerializer(read_only=True)
    actor = AccessUserSnapshotSerializer(read_only=True)

    class Meta:
        model = AuditEvent
        fields = ["id", "company", "branch", "actor", "category", "action", "severity", "target_app", "target_model", "target_id", "target_label", "description", "occurred_at"]
        read_only_fields = fields