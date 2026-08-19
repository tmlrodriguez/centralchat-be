from rest_framework import serializers
from access.serializers.snapshots import AccessUserSnapshotSerializer
from organizations.serializers.snapshots import CompanySnapshotSerializer
from .snapshots import CustomerSnapshotSerializer, MediaAttachmentSnapshotSerializer, MessageSnapshotSerializer
from ..models import NumberAssignment, WhatsAppBusinessAccount, WhatsAppNumber, Conversation, Customer, MediaAttachment, Message

# Define your serializers here.

class WhatsAppBusinessAccountSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: WhatsApp Business Account Serializer

        Description:
        - Serialize and validate the primary WhatsApp Business Account resource.

        Notes:
        - The company is derived from the URL and controlled by the backend.
        - Credential references identify external secret configuration and must not expose actual credentials.
        - Temporal and author fields are controlled exclusively by the backend.
    """
    company = CompanySnapshotSerializer(read_only=True)
    created_by = AccessUserSnapshotSerializer(read_only=True)
    updated_by = AccessUserSnapshotSerializer(read_only=True)

    class Meta:
        model = WhatsAppBusinessAccount
        fields = ["id", "company", "meta_waba_id", "meta_business_id", "display_name", "is_connected", "is_webhook_configured", "connected_at", "disconnected_at", "notes", "is_active", "created_at", "updated_at", "created_by", "updated_by"]
        read_only_fields = ["id", "company", "is_connected", "is_webhook_configured", "connected_at", "disconnected_at", "created_at", "updated_at", "created_by", "updated_by"]


class WhatsAppNumberSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: WhatsApp Number Serializer

        Description:
        - Serialize and validate the primary corporate WhatsApp number resource.

        Notes:
        - Company and branch context are controlled by the backend.
        - The selected WhatsApp Business Account must belong to the same active company.
        - Monitoring lifecycle fields cannot be manipulated through this serializer.
        - Temporal and author fields are controlled exclusively by the backend.
    """

    company = CompanySnapshotSerializer(read_only=True)
    created_by = AccessUserSnapshotSerializer(read_only=True)
    updated_by = AccessUserSnapshotSerializer(read_only=True)

    class Meta:
        model = WhatsAppNumber
        fields = ["id", "company", "branch", "whatsapp_business_account", "phone_number", "display_name", "meta_phone_number_id", "is_connected", "is_monitoring_enabled", "monitoring_started_at", "monitoring_stopped_at", "notes", "is_active", "created_at", "updated_at", "created_by", "updated_by"]
        read_only_fields = ["id", "company", "branch", "is_monitoring_enabled", "monitoring_started_at", "monitoring_stopped_at", "created_at", "updated_at", "created_by", "updated_by"]

    def validate_whatsapp_business_account(self, value):
        company = self.context.get("company")
        if company is None:
            raise serializers.ValidationError("Asignación de cuenta rechazada: no se pudo determinar la empresa.")
        if value.company_id != company.id:
            raise serializers.ValidationError("Asignación de cuenta rechazada: la cuenta de WhatsApp Business no pertenece a la empresa.")
        if not value.is_active:
            raise serializers.ValidationError("Asignación de cuenta rechazada: la cuenta de WhatsApp Business se encuentra inactiva.")
        return value


class NumberAssignmentSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Number Assignment Serializer

        Description:
        - Validate assignment of a company member to a corporate WhatsApp number.

        Notes:
        - The WhatsApp number is determined by the URL and controlled by the backend.
        - The member must belong to the same company and branch as the WhatsApp number.
        - Historical lifecycle fields are controlled by the backend.
    """
    class Meta:
        model = NumberAssignment
        fields = ["id", "whatsapp_number", "member", "assigned_at", "unassigned_at", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "whatsapp_number", "assigned_at", "unassigned_at", "is_active", "created_at", "updated_at"]

    def validate_member(self, value):
        whatsapp_number = self.context.get("whatsapp_number")
        if whatsapp_number is None:
            raise serializers.ValidationError("Asignación de número rechazada: no se pudo determinar el número de WhatsApp.")
        if value.company_id != whatsapp_number.company_id:
            raise serializers.ValidationError("Asignación de número rechazada: el miembro no pertenece a la misma empresa.")
        if value.branch_id != whatsapp_number.branch_id:
            raise serializers.ValidationError("Asignación de número rechazada: el miembro no pertenece a la misma sucursal.")
        if not value.is_active:
            raise serializers.ValidationError("Asignación de número rechazada: el miembro seleccionado se encuentra inactivo.")
        return value


class CustomerSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Customer Serializer

        Description:
        - Provide the detailed read-only representation of an external WhatsApp participant.

        Notes:
        - Customer records are automatically maintained by the WhatsApp ingestion layer.
        - Customer records must not be manually created or modified through monitoring endpoints.
        - Customer data remains limited to monitoring identity information.
    """
    class Meta:
        model = Customer
        fields = ["id", "phone_number", "display_name", "profile_name", "is_active", "created_at", "updated_at"]
        read_only_fields = fields


class MediaAttachmentSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Media Attachment Serializer

        Description:
        - Provide detailed metadata for a monitored WhatsApp media attachment.

        Notes:
        - Internal object-storage keys must never be exposed through the API.
        - Media binaries are retrieved through a separately authorized mechanism.
        - Attachment records are created by the WhatsApp ingestion layer.
    """
    class Meta:
        model = MediaAttachment
        fields = ["id", "meta_media_id", "mime_type", "size", "original_filename", "checksum", "is_stored", "is_active", "created_at", "updated_at"]
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Message Serializer

        Description:
        - Provide the detailed read-only representation of a monitored WhatsApp message.
        - Include associated media attachment metadata.

        Notes:
        - Messages are persisted by the WhatsApp ingestion layer.
        - Message content cannot be created, edited, or deleted by monitoring users.
        - Internal Meta payloads and object-storage identifiers must not be exposed.
    """
    media_attachments = MediaAttachmentSnapshotSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = ["id", "meta_message_id", "direction", "message_type", "sender_phone_number", "recipient_phone_number", "text_body", "message_timestamp", "meta_event_timestamp", "revoked_at", "edited_message", "media_attachments", "is_active", "created_at", "updated_at"]
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Conversation Serializer

        Description:
        - Provide the detailed read-only representation of a monitored WhatsApp conversation.

        Notes:
        - Customer identity is included through a compact snapshot.
        - Complete message history is retrieved through the dedicated message endpoint.
        - Conversation records are maintained by the WhatsApp ingestion layer.
    """ 
    customer = CustomerSnapshotSerializer(read_only=True)
    last_message = MessageSnapshotSerializer(read_only=True)

    class Meta:
        model = Conversation
        fields = ["id", "customer", "last_message", "last_message_at", "is_active", "created_at", "updated_at"]
        read_only_fields = fields