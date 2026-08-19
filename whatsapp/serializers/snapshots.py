from rest_framework import serializers
from members.serializers.snapshots import MemberSnapshotSerializer
from organizations.serializers.snapshots import BranchSnapshotSerializer, CompanySnapshotSerializer
from ..models import NumberAssignment, WhatsAppBusinessAccount, WhatsAppNumber, Conversation, ConversationReadState, Customer, MediaAttachment, Message

# Define your serializers here.

class WhatsAppBusinessAccountSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: WhatsApp Business Account Snapshot Serializer

        Description:
        - Provide a compact read-only representation of a WhatsApp Business Account.

        Notes:
        - Credential references are intentionally excluded.
        - Snapshot serializers must remain read-only.
    """
    class Meta:
        model = WhatsAppBusinessAccount
        fields = ["id", "display_name", "meta_waba_id", "is_connected", "is_webhook_configured", "is_active"]
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
        - Media metadata is retrieved separately when required.
        - All fields exposed by this serializer are read-only.
    """
    class Meta:
        model = Message
        fields = ["id", "meta_message_id", "direction", "message_type", "text_body", "message_timestamp", "revoked_at"]
        read_only_fields = fields


class MediaAttachmentSnapshotSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Media Attachment Snapshot Serializer

        Description:
        - Provide a compact read-only representation of media metadata associated with a monitored message.

        Notes:
        - Private object storage identifiers must not be exposed.
        - Binary media retrieval will be handled separately through authorized signed URLs.
        - All fields exposed by this serializer are read-only.
    """
    class Meta:
        model = MediaAttachment
        fields = ["id", "meta_media_id", "mime_type", "size", "original_filename", "is_stored"]
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
        - Include customer identity, latest message information, and authenticated-user read state.

        Notes:
        - The read state is resolved from the serializer context.
        - Conversation lists use this serializer to avoid retrieving complete message histories.
        - All exposed fields are read-only.
    """

    customer = CustomerSnapshotSerializer(read_only=True)
    last_message = MessageSnapshotSerializer(read_only=True)
    is_read = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "customer", "last_message", "last_message_at", "is_read", "unread_count", "is_active"]
        read_only_fields = fields

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