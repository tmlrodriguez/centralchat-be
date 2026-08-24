from rest_framework import serializers
from access.serializers.snapshots import AccessUserSnapshotSerializer
from organizations.serializers.snapshots import BranchSnapshotSerializer, CompanySnapshotSerializer
from ..models import AuditEvent

# Define your auditing serializers here.

class AuditEventSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Audit Event Serializer

        Description:
        - Provide the detailed read-only representation of an immutable CentralChat audit event.

        Notes:
        - Audit events cannot be created, updated, or deleted through this serializer.
        - Sensitive authentication material is never stored in metadata.
        - Request metadata is exposed only for administrative traceability.
    """

    company = CompanySnapshotSerializer(read_only=True)
    branch = BranchSnapshotSerializer(read_only=True)
    actor = AccessUserSnapshotSerializer(read_only=True)

    class Meta:
        model = AuditEvent
        fields = ["id", "company", "branch", "actor", "category", "action", "severity", "target_app", "target_model", "target_id", "target_label", "description", "metadata", "request_id", "ip_address", "user_agent", "occurred_at"]
        read_only_fields = fields