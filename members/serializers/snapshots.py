from rest_framework import serializers
from organizations.serializers.snapshots import BranchSnapshotSerializer, CompanySnapshotSerializer
from ..models import Member, Position


class PositionSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Position Snapshot Serializer

        Description:
        - Provide a compact read-only representation of a Dialoqo position.

        Notes:
        - Snapshot serializers must remain read-only.
        - This serializer is intended for lightweight and nested representations.
    """

    class Meta:
        model = Position
        fields = ["id", "name", "code", "is_active"]
        read_only_fields = fields


class MemberSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Member Snapshot Serializer

        Description:
        - Provide a compact read-only representation of a Dialoqo member.

        Notes:
        - Company, branch, and position relationships use their corresponding snapshot serializers.
        - Snapshot serializers must remain read-only.
    """

    company = CompanySnapshotSerializer(read_only=True)
    branch = BranchSnapshotSerializer(read_only=True)
    position = PositionSnapshotSerializer(read_only=True)

    class Meta:
        model = Member
        fields = ["id", "company", "branch", "position", "member_code", "first_name", "last_name", "email", "is_active"]
        read_only_fields = fields