from rest_framework import serializers

from members.serializers.snapshots import MemberSnapshotSerializer
from organizations.serializers.snapshots import BranchSnapshotSerializer, CompanySnapshotSerializer

from ..models import Conversation, ConversationReadState, Customer, MediaAttachment, Message, MetaIntegration, NumberAssignment, WhatsAppBusinessAccount, WhatsAppNumber


# Define your serializers here.

class MetaIntegrationSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Meta Integration Snapshot Serializer

        Description:
        - Provide a compact read-only representation of a company Meta integration.

        Notes:
        - Sensitive credentials and credential references are intentionally excluded.
        - webhook_key is intentionally excluded from normal snapshot responses.
        - Snapshot serializers must remain read-only.
    """

    class Meta:
        model = MetaIntegration
        fields = ["id", "meta_app_id", "is_connected", "is_active"]
        read_only_fields = fields


class WhatsAppBusinessAccountSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: WhatsApp Business Account Snapshot Serializer

        Description:
        - Provide a compact read-only representation of a WhatsApp Business Account.

        Notes:
        - The associated Meta integration is represented through its compact snapshot.
        - Sensitive Meta credentials are intentionally excluded.
        - Snapshot serializers must remain read-only.
    """

    meta_integration = MetaIntegrationSnapshotSerializer(read_only=True)

    class Meta:
        model = WhatsAppBusinessAccount
        fields = ["id", "meta_integration", "display_name", "meta_waba_id", "is_connected", "is_webhook_configured", "is_active"]
        read_only_fields = fields


class WhatsAppNumberSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: WhatsApp Number Snapshot Serializer

        Description:
        - Provide a compact read-only representation of a corporate WhatsApp number.

        Notes:
        - Company, branch, and WhatsApp Business Account relationships use their corresponding snapshot serializers.
        - Monitoring lifecycle fields are exposed as read-only information.
        - Snapshot serializers must remain read-only.
    """

    company = CompanySnapshotSerializer(read_only=True)
    branch = BranchSnapshotSerializer(read_only=True)
    whatsapp_business_account = WhatsAppBusinessAccountSnapshotSerializer(read_only=True)

    class Meta:
        model = WhatsAppNumber
        fields = ["id", "company", "branch", "whatsapp_business_account", "phone_number", "display_name", "is_connected", "is_monitoring_enabled", "monitoring_started_at", "monitoring_stopped_at", "is_active"]
        read_only_fields = fields


class NumberAssignmentSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Number Assignment Snapshot Serializer

        Description:
        - Provide a compact read-only representation of a WhatsApp number assignment.

        Notes:
        - The member relationship is represented through MemberSnapshotSerializer.
        - Historical assignment information must remain read-only.
        - is_active identifies whether the assignment represents current responsibility or historical responsibility.
    """

    member = MemberSnapshotSerializer(read_only=True)

    class Meta:
        model = NumberAssignment
        fields = ["id", "member", "assigned_at", "unassigned_at", "is_active"]
        read_only_fields = fields


class CustomerSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Customer Snapshot Serializer

        Description:
        - Provide a compact read-only representation of an external WhatsApp participant.

        Notes:
        - Customer records are monitoring identity records and not CRM records.
        - All fields exposed by this serializer are read-only.
    """

    class Meta:
        model = Customer
        fields = ["id", "phone_number", "display_name", "profile_name"]
        read_only_fields = fields


class MessageSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Message Snapshot Serializer

        Description:
        - Provide a compact read-only representation of a monitored WhatsApp message.
        - Support conversation previews and lightweight message rendering.

        Notes:
        - Revoked messages must not expose previous text or structured content.
        - display_text contains the value the frontend should render.
        - All exposed fields are read-only.
    """

    text_body = serializers.SerializerMethodField()
    content_data = serializers.SerializerMethodField()
    display_text = serializers.CharField(read_only=True)
    is_edited = serializers.BooleanField(read_only=True)
    is_revoked = serializers.BooleanField(read_only=True)
    context_message_id = serializers.IntegerField(source="context_message.id", read_only=True, allow_null=True)

    class Meta:
        model = Message
        fields = ["id", "meta_message_id", "direction", "message_type", "status", "text_body", "display_text", "content_data", "context_message_id", "message_timestamp", "is_edited", "edited_at", "is_revoked", "revoked_at"]
        read_only_fields = fields

    def get_text_body(self, obj):
        if obj.is_revoked:
            return ""

        return obj.text_body

    def get_content_data(self, obj):
        if obj.is_revoked:
            return {}

        return obj.content_data


class MediaAttachmentSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Media Attachment Snapshot Serializer

        Description:
        - Provide a compact read-only representation of media metadata and storage availability associated with a monitored message.

        Notes:
        - Private storage identifiers must not be exposed.
        - Binary media retrieval is handled separately through the authenticated content endpoint.
        - All fields exposed by this serializer are read-only.
    """

    class Meta:
        model = MediaAttachment
        fields = ["id", "meta_media_id", "mime_type", "size", "original_filename", "storage_status", "is_stored", "stored_at"]
        read_only_fields = fields


class ConversationReadStateSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Conversation Read State Snapshot Serializer

        Description:
        - Provide the authenticated monitoring user's current read state for a conversation.

        Notes:
        - Read state belongs independently to each monitoring user.
        - unread_count represents messages not yet acknowledged by the monitoring user.
        - All fields exposed by this serializer are read-only.
    """

    last_read_message = MessageSnapshotSerializer(read_only=True)

    class Meta:
        model = ConversationReadState
        fields = ["is_read", "unread_count", "last_read_message", "last_opened_at"]
        read_only_fields = fields


class ConversationSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Conversation Snapshot Serializer

        Description:
        - Provide a compact representation of a monitored WhatsApp conversation.
        - Include customer identity, latest message information, authenticated-user read state, and current number assignment.

        Notes:
        - Read state is resolved from the serializer context.
        - Current assignment is resolved once for the owning WhatsApp number and supplied through serializer context.
        - Conversation lists avoid querying assignment information individually for every conversation.
        - All exposed fields are read-only.
    """

    customer = CustomerSnapshotSerializer(read_only=True)
    last_message = MessageSnapshotSerializer(read_only=True)
    current_assignment = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "customer", "current_assignment", "last_message", "last_message_at", "is_read", "unread_count", "is_active"]
        read_only_fields = fields

    def get_current_assignment(self, obj):
        current_assignment = self.context.get("current_assignment")

        if current_assignment is None:
            return None

        return NumberAssignmentSnapshotSerializer(current_assignment).data

    def get_is_read(self, obj):
        request = self.context.get("request")

        if not request:
            return False

        read_state = getattr(obj, "current_user_read_state", None)

        if not read_state:
            return False

        return read_state.is_read

    def get_unread_count(self, obj):
        request = self.context.get("request")

        if not request:
            return 0

        read_state = getattr(obj, "current_user_read_state", None)

        if not read_state:
            return 0

        return read_state.unread_count