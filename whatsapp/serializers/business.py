from rest_framework import serializers

from access.serializers.snapshots import AccessUserSnapshotSerializer
from organizations.serializers.snapshots import CompanySnapshotSerializer

from .snapshots import CustomerSnapshotSerializer, MediaAttachmentSnapshotSerializer, MessageSnapshotSerializer, NumberAssignmentSnapshotSerializer
from ..models import Conversation, Customer, MediaAttachment, Message, MetaIntegration, NumberAssignment, WhatsAppBusinessAccount, WhatsAppNumber


# Define your serializers here.

class MetaIntegrationSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Meta Integration Serializer

        Description:
        - Serialize and validate the Meta application integration configured for a CentralChat company.

        Notes:
        - The company is derived from the URL and controlled by the backend.
        - Sensitive Meta credentials must never be exposed through this serializer.
        - credential_reference identifies the corresponding entry in the secure credential store.
        - webhook_key is generated exclusively by the backend.
        - Connection lifecycle fields are controlled exclusively by the backend.
        - Temporal and author fields are controlled exclusively by the backend.
    """

    company = CompanySnapshotSerializer(read_only=True)
    created_by = AccessUserSnapshotSerializer(read_only=True)
    updated_by = AccessUserSnapshotSerializer(read_only=True)

    class Meta:
        model = MetaIntegration
        fields = ["id", "company", "meta_app_id", "credential_reference", "webhook_key", "is_connected", "connected_at", "disconnected_at", "notes", "is_active", "created_at", "updated_at", "created_by", "updated_by"]
        read_only_fields = ["id", "company", "webhook_key", "is_connected", "connected_at", "disconnected_at", "created_at", "updated_at", "created_by", "updated_by"]


class WhatsAppBusinessAccountSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: WhatsApp Business Account Serializer

        Description:
        - Serialize and validate the primary WhatsApp Business Account resource.

        Notes:
        - The company is derived from the URL and controlled by the backend.
        - The selected Meta integration must belong to the same active company.
        - Sensitive Meta credentials are not exposed through this serializer.
        - Connection and webhook lifecycle fields are controlled exclusively by the backend.
        - Temporal and author fields are controlled exclusively by the backend.
    """

    company = CompanySnapshotSerializer(read_only=True)
    created_by = AccessUserSnapshotSerializer(read_only=True)
    updated_by = AccessUserSnapshotSerializer(read_only=True)

    class Meta:
        model = WhatsAppBusinessAccount
        fields = ["id", "company", "meta_integration", "meta_waba_id", "meta_business_id", "display_name", "is_connected", "is_webhook_configured", "connected_at", "disconnected_at", "notes", "is_active", "created_at", "updated_at", "created_by", "updated_by"]
        read_only_fields = ["id", "company", "is_connected", "is_webhook_configured", "connected_at", "disconnected_at", "created_at", "updated_at", "created_by", "updated_by"]

    def validate_meta_integration(self, value):
        company = self.context.get("company")

        if company is None:
            raise serializers.ValidationError("Asignación de integración rechazada: no se pudo determinar la empresa.")

        if value.company_id != company.id:
            raise serializers.ValidationError("Asignación de integración rechazada: la integración de Meta no pertenece a la empresa.")

        if not value.is_active:
            raise serializers.ValidationError("Asignación de integración rechazada: la integración de Meta se encuentra inactiva.")

        return value


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
        read_only_fields = ["id", "company", "branch", "is_connected", "is_monitoring_enabled", "monitoring_started_at", "monitoring_stopped_at", "created_at", "updated_at", "created_by", "updated_by"]

    def validate_whatsapp_business_account(self, value):
        company = self.context.get("company")

        if company is None:
            raise serializers.ValidationError("Asignación de cuenta rechazada: no se pudo determinar la empresa.")

        if value.company_id != company.id:
            raise serializers.ValidationError("Asignación de cuenta rechazada: la cuenta de WhatsApp Business no pertenece a la empresa.")

        if not value.is_active:
            raise serializers.ValidationError("Asignación de cuenta rechazada: la cuenta de WhatsApp Business se encuentra inactiva.")

        if not value.meta_integration.is_active:
            raise serializers.ValidationError("Asignación de cuenta rechazada: la integración de Meta asociada se encuentra inactiva.")

        return value


class NumberAssignmentSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Number Assignment Serializer

        Description:
        - Validate assignment of a company member to a corporate WhatsApp number.

        Notes:
        - The WhatsApp number is determined by the URL and controlled by the backend.
        - The member must belong to the same company and branch as the WhatsApp number.
        - The member must remain active.
        - Historical lifecycle fields are controlled by the backend.
        - Assignment invariants are validated again inside the transactional operation layer.
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
        - Provide detailed metadata and private-storage state for a monitored WhatsApp media attachment.

        Notes:
        - Internal object-storage keys must never be exposed through the API.
        - Media binaries are retrieved through the separately authorized content endpoint.
        - Attachment records are created by the WhatsApp ingestion layer.
        - Internal storage failure details are intentionally excluded from monitoring responses.
    """

    class Meta:
        model = MediaAttachment
        fields = ["id", "meta_media_id", "mime_type", "size", "original_filename", "checksum", "storage_status", "is_stored", "stored_at", "is_active", "created_at", "updated_at"]
        read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Message Serializer

        Description:
        - Provide the detailed read-only representation of a monitored WhatsApp message.
        - Include lifecycle state, structured content, context, and media metadata.

        Notes:
        - Messages are maintained by the WhatsApp ingestion layer.
        - Revoked text and structured content must not be exposed to monitoring users.
        - Internal object-storage identifiers and raw webhook payloads are not exposed.
    """

    text_body = serializers.SerializerMethodField()
    content_data = serializers.SerializerMethodField()
    display_text = serializers.CharField(read_only=True)
    is_edited = serializers.BooleanField(read_only=True)
    is_revoked = serializers.BooleanField(read_only=True)
    context_message_id = serializers.IntegerField(source="context_message.id", read_only=True, allow_null=True)
    media_attachments = MediaAttachmentSnapshotSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = ["id", "meta_message_id", "direction", "message_type", "status", "sender_phone_number", "recipient_phone_number", "text_body", "display_text", "content_data", "context_message_id", "message_timestamp", "meta_event_timestamp", "status_updated_at", "sent_at", "delivered_at", "read_at", "failed_at", "failure_code", "failure_message", "is_edited", "edited_at", "is_revoked", "revoked_at", "media_attachments", "is_active", "created_at", "updated_at"]
        read_only_fields = fields

    def get_text_body(self, obj):
        if obj.is_revoked:
            return ""

        return obj.text_body

    def get_content_data(self, obj):
        if obj.is_revoked:
            return {}

        return obj.content_data


class ConversationSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Conversation Serializer

        Description:
        - Provide the detailed read-only representation of a monitored WhatsApp conversation.
        - Include the current member assignment responsible for the owning WhatsApp number.

        Notes:
        - Customer identity is included through a compact snapshot.
        - Complete message history is retrieved through the dedicated message endpoint.
        - Current assignment is supplied through serializer context to prevent additional assignment queries.
        - Conversation records are maintained by the WhatsApp ingestion layer.
    """

    customer = CustomerSnapshotSerializer(read_only=True)
    current_assignment = serializers.SerializerMethodField()
    last_message = MessageSnapshotSerializer(read_only=True)

    class Meta:
        model = Conversation
        fields = ["id", "customer", "current_assignment", "last_message", "last_message_at", "is_active", "created_at", "updated_at"]
        read_only_fields = fields

    def get_current_assignment(self, obj):
        current_assignment = self.context.get("current_assignment")

        if current_assignment is None:
            return None

        return NumberAssignmentSnapshotSerializer(current_assignment).data


class OutboundTextMessageSerializer(serializers.Serializer):
    """
        DOCSTRING: Outbound Text Message Serializer

        Description:
        - Validate a plain-text WhatsApp message submitted by the CentralChat frontend for outbound delivery.

        Notes:
        - The destination customer is determined from the conversation and cannot be supplied by the client.
        - The corporate WhatsApp number is determined from the URL and cannot be supplied by the client.
        - Empty and whitespace-only messages are rejected.
        - Message lifecycle information is controlled exclusively by the backend.
    """

    text_body = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True, max_length=4096)

    def validate_text_body(self, value):
        if not value.strip():
            raise serializers.ValidationError("Envío de mensaje rechazado: el contenido del mensaje no puede estar vacío.")

        return value