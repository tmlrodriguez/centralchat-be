from rest_framework import serializers
from ..models import AccessUser

# Define your serializers here.

class AccessUserSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: User Snapshot Serializer

        Description:
        - Provide a compact read-only representation of a CentralChat user.

        Notes:
        - This serializer is intended for nested representations and lightweight references.
        - Passwords and Django permission information must never be exposed.
        - Snapshot serializers must remain read-only.
    """
    class Meta:
        model = AccessUser
        fields = ["id", "username", "first_name", "last_name", "role"]
        read_only_fields = fields