from rest_framework import serializers
from .snapshots import MetaIntegrationSnapshotSerializer, WhatsAppBusinessAccountSnapshotSerializer, WhatsAppNumberSnapshotSerializer

# Define your serializers here.

class MetaIntegrationValidationResultSerializer(serializers.Serializer):
    """
        DOCSTRING: Meta Integration Validation Result Serializer

        Description:
        - Represent the result of validating Meta integration credentials.
    """

    meta_integration = MetaIntegrationSnapshotSerializer(read_only=True)
    meta_identity = serializers.JSONField(read_only=True)


class WhatsAppNumberValidationResultSerializer(serializers.Serializer):
    """
        DOCSTRING: WhatsApp Number Validation Result Serializer

        Description:
        - Represent actual Meta validation state for one configured WhatsApp number.
    """

    whatsapp_number = WhatsAppNumberSnapshotSerializer(read_only=True)
    meta_phone = serializers.JSONField(read_only=True)


class WhatsAppBusinessAccountLifecycleResultSerializer(serializers.Serializer):
    """
        DOCSTRING: WhatsApp Business Account Lifecycle Result Serializer

        Description:
        - Represent WABA lifecycle synchronization results.
    """

    meta_integration = MetaIntegrationSnapshotSerializer(read_only=True, required=False)
    whatsapp_business_account = WhatsAppBusinessAccountSnapshotSerializer(read_only=True)
    meta_waba = serializers.JSONField(read_only=True, required=False)
    subscribed_apps = serializers.JSONField(read_only=True)
    numbers = serializers.JSONField(read_only=True, required=False)