from rest_framework import serializers

from ..models import WhatsAppMessageTemplate
from ..registry import MESSAGE_TEMPLATE_CATEGORY_REGISTRY, MESSAGE_TEMPLATE_PARAMETER_FORMAT_REGISTRY


# Define your template serializers here.

class WhatsAppMessageTemplateSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: WhatsApp Message Template Serializer

        Description:
        - Provide a detailed read-only representation of a synchronized WhatsApp message template.

        Notes:
        - Template lifecycle fields originate from Meta.
        - Raw credentials are never exposed.
    """

    class Meta:
        model = WhatsAppMessageTemplate
        fields = ["id", "meta_template_id", "name", "language", "category", "status", "parameter_format", "components", "quality_score", "rejection_reason", "is_available_in_meta", "last_synced_at", "removed_from_meta_at", "is_active", "created_at", "updated_at"]
        read_only_fields = fields


class WhatsAppMessageTemplateSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: WhatsApp Message Template Snapshot Serializer

        Description:
        - Provide a compact template representation used by selection interfaces.

        Notes:
        - Components remain available because the frontend needs them to collect template parameters.
    """

    class Meta:
        model = WhatsAppMessageTemplate
        fields = ["id", "name", "language", "category", "status", "parameter_format", "components"]
        read_only_fields = fields


class WhatsAppMessageTemplateCreateSerializer(serializers.Serializer):
    """
        DOCSTRING: WhatsApp Message Template Create Serializer

        Description:
        - Validate a new template definition before submission to Meta.

        Notes:
        - Meta performs final validation and approval review.
    """

    name = serializers.RegexField(regex=r"^[a-z0-9_]+$", max_length=512)
    language = serializers.CharField(max_length=50)
    category = serializers.ChoiceField(choices=MESSAGE_TEMPLATE_CATEGORY_REGISTRY.choices)
    parameter_format = serializers.ChoiceField(choices=MESSAGE_TEMPLATE_PARAMETER_FORMAT_REGISTRY.choices, default=MESSAGE_TEMPLATE_PARAMETER_FORMAT_REGISTRY.POSITIONAL)
    components = serializers.ListField(child=serializers.DictField(), allow_empty=False)


class WhatsAppMessageTemplateUpdateSerializer(serializers.Serializer):
    """
        DOCSTRING: WhatsApp Message Template Update Serializer

        Description:
        - Validate supported modifications to an existing Meta message template.

        Notes:
        - Meta determines whether the current template state permits modification.
    """

    category = serializers.ChoiceField(choices=MESSAGE_TEMPLATE_CATEGORY_REGISTRY.choices, required=False)
    components = serializers.ListField(child=serializers.DictField(), required=False, allow_empty=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Actualización de plantilla rechazada: no se proporcionaron cambios.")

        return attrs


class TemplateSendSerializer(serializers.Serializer):
    """
        DOCSTRING: Template Send Serializer

        Description:
        - Validate a request to send an approved template into an existing conversation.

        Notes:
        - Destination customer and WhatsApp number come exclusively from the conversation hierarchy.
    """

    template_id = serializers.IntegerField(min_value=1)
    components = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class NewConversationTemplateSendSerializer(serializers.Serializer):
    """
        DOCSTRING: New Conversation Template Send Serializer

        Description:
        - Validate a business-initiated template message sent to a phone number with no required existing conversation.

        Notes:
        - Customer and conversation records are created only after Meta accepts the message.
    """

    recipient_phone_number = serializers.CharField(max_length=30)
    template_id = serializers.IntegerField(min_value=1)
    components = serializers.ListField(child=serializers.DictField(), required=False, default=list)