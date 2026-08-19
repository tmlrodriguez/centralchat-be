from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from common.mixins import AuthorMixin, LifeCycleMixin, TemporalMixin
from members.models import Member
from organizations.models import Branch, Company
from .registry import MESSAGE_DIRECTION_REGISTRY, MESSAGE_TYPE_REGISTRY

# Define your models here.

class WhatsAppBusinessAccount(TemporalMixin, LifeCycleMixin, AuthorMixin):
    """
        DOCSTRING: WhatsApp Business Account

        Description:
        - Represent a Meta WhatsApp Business Account configured in CentralChat.
        - Group one or more corporate WhatsApp numbers under the corresponding company integration.

        Notes:
        - A WhatsApp Business Account belongs to exactly one company.
        - Meta credentials must not be stored directly in this model.
        - credential_reference identifies the external secret or credential configuration used by the integration.
        - Records are deactivated instead of destructively deleted.
    """
    company = models.ForeignKey(Company, blank=False, null=False, on_delete=models.PROTECT, related_name="whatsapp_business_accounts")
    meta_waba_id = models.CharField(max_length=100, blank=False, null=False, unique=True)
    meta_business_id = models.CharField(max_length=100, blank=False, null=False)
    display_name = models.CharField(max_length=150, blank=False, null=False)
    is_connected = models.BooleanField(default=False)
    is_webhook_configured = models.BooleanField(default=False)
    connected_at = models.DateTimeField(blank=True, null=True)
    disconnected_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=False, default="")

    class Meta:
        db_table = "whatsapp_business_account"
        ordering = ["display_name"]
        indexes = [
            models.Index(fields=["company", "is_active"], name="idx_waba_company_active"),
            models.Index(fields=["company", "is_connected"], name="idx_waba_company_connected"),
        ]

    def __str__(self):
        return self.display_name


class WhatsAppNumber(TemporalMixin, LifeCycleMixin, AuthorMixin):
    """
        DOCSTRING: WhatsApp Number

        Description:
        - Represent a corporate WhatsApp number registered in CentralChat.
        - Associate the number with its company, branch, and WhatsApp Business Account.

        Notes:
        - The branch and WhatsApp Business Account must belong to the same company as the number.
        - meta_phone_number_id uniquely identifies the number in Meta.
        - Monitoring begins only through an explicit monitoring activation operation.
        - Historical WhatsApp synchronization before monitoring_started_at is outside the MVP.
        - Records are deactivated instead of destructively deleted.
    """
    company = models.ForeignKey(Company, blank=False, null=False, on_delete=models.PROTECT, related_name="whatsapp_numbers")
    branch = models.ForeignKey(Branch, blank=False, null=False, on_delete=models.PROTECT, related_name="whatsapp_numbers")
    whatsapp_business_account = models.ForeignKey(WhatsAppBusinessAccount, blank=False, null=False, on_delete=models.PROTECT, related_name="numbers")
    phone_number = models.CharField(max_length=30, blank=False, null=False, unique=True)
    display_name = models.CharField(max_length=150, blank=False, null=False)
    meta_phone_number_id = models.CharField(max_length=100, blank=False, null=False, unique=True)
    is_connected = models.BooleanField(default=False)
    is_monitoring_enabled = models.BooleanField(default=False)
    monitoring_started_at = models.DateTimeField(blank=True, null=True)
    monitoring_stopped_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=False, default="")

    class Meta:
        db_table = "whatsapp_number"
        ordering = ["display_name"]
        indexes = [
            models.Index(fields=["company", "is_active"], name="idx_wa_number_company_active"),
            models.Index(fields=["branch", "is_active"], name="idx_wa_number_branch_active"),
            models.Index(fields=["whatsapp_business_account", "is_active"], name="idx_wa_number_waba_active"),
            models.Index(fields=["meta_phone_number_id"], name="idx_wa_number_meta_id"),
            models.Index(fields=["company", "is_monitoring_enabled"], name="idx_wa_number_monitoring"),
        ]

    def __str__(self):
        return f"{self.display_name} - {self.phone_number}"


class NumberAssignment(TemporalMixin, LifeCycleMixin, AuthorMixin):
    """
        DOCSTRING: Number Assignment

        Description:
        - Represent the historical assignment of a WhatsApp number to a company member.
        - Preserve responsibility history when a WhatsApp number is reassigned.

        Notes:
        - Only one active assignment may exist for a WhatsApp number.
        - The member must belong to the same company and branch as the WhatsApp number.
        - Reassignment must close the existing assignment before creating the new assignment.
        - Historical assignments must never be overwritten or deleted.
    """
    whatsapp_number = models.ForeignKey(WhatsAppNumber, blank=False, null=False, on_delete=models.PROTECT, related_name="assignments")
    member = models.ForeignKey(Member, blank=False, null=False, on_delete=models.PROTECT, related_name="whatsapp_number_assignments")
    assigned_at = models.DateTimeField(default=timezone.now)
    unassigned_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "whatsapp_number_assignment"
        ordering = ["-assigned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["whatsapp_number"],
                condition=Q(is_active=True),
                name="unique_active_whatsapp_number_assignment",
            ),
            models.CheckConstraint(
                condition=Q(unassigned_at__isnull=True) | Q(unassigned_at__gte=models.F("assigned_at")),
                name="assignment_unassigned_after_assigned",
            ),
        ]
        indexes = [
            models.Index(fields=["whatsapp_number", "is_active"], name="idx_assignment_number_active"),
            models.Index(fields=["member", "is_active"], name="idx_assignment_member_active"),
            models.Index(fields=["whatsapp_number", "assigned_at"], name="idx_assignment_number_date"),
        ]

    def __str__(self):
        return f"{self.whatsapp_number.phone_number} - {self.member}"


class Customer(TemporalMixin, LifeCycleMixin, AuthorMixin):
    """
    DOCSTRING: Customer

    Description:
    - Represent the external WhatsApp participant communicating with a company-owned WhatsApp number.
    - Provide a minimal company-scoped identity used to organize monitored conversations.

    Notes:
    - Customer records are not CRM records.
    - A customer belongs to exactly one company context.
    - The same phone number may exist independently under different companies.
    - Customer phone numbers must be unique within each company.
    - The model must remain limited to identity information required for conversation monitoring.
    """

    company = models.ForeignKey(Company, blank=False, null=False, on_delete=models.PROTECT, related_name="customers")
    phone_number = models.CharField(max_length=30, blank=False, null=False)
    display_name = models.CharField(max_length=150, blank=True, null=False, default="")
    profile_name = models.CharField(max_length=150, blank=True, null=False, default="")

    class Meta:
        db_table = "whatsapp_customer"
        ordering = ["phone_number"]
        constraints = [
            models.UniqueConstraint(fields=["company", "phone_number"], name="unique_customer_phone_per_company"),
        ]
        indexes = [
            models.Index(fields=["company", "is_active"], name="idx_customer_company_active"),
            models.Index(fields=["company", "phone_number"], name="idx_customer_company_phone"),
        ]

    def __str__(self):
        return self.display_name or self.profile_name or self.phone_number


class Conversation(TemporalMixin, LifeCycleMixin, AuthorMixin):
    """
    DOCSTRING: Conversation

    Description:
    - Represent the monitored conversation between one corporate WhatsApp number and one customer.
    - Provide the parent record used to organize persisted monitored messages.
    - Maintain the latest message information required for efficient conversation listing.

    Notes:
    - A conversation belongs to exactly one WhatsApp number and one customer.
    - The customer must belong to the same company as the WhatsApp number.
    - Only one conversation may exist for the same WhatsApp number and customer.
    - last_message references the most recently persisted message in the conversation.
    - last_message_at supports efficient ordering without aggregating the complete message history.
    - Read and unread state is maintained independently per monitoring user through ConversationReadState.
    """

    whatsapp_number = models.ForeignKey(WhatsAppNumber, blank=False, null=False, on_delete=models.PROTECT, related_name="conversations")
    customer = models.ForeignKey(Customer, blank=False, null=False, on_delete=models.PROTECT, related_name="conversations")
    last_message = models.ForeignKey("Message", blank=True, null=True, on_delete=models.SET_NULL, related_name="+")
    last_message_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "whatsapp_conversation"
        ordering = ["-last_message_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["whatsapp_number", "customer"], name="unique_conversation_per_number_customer"),
        ]
        indexes = [
            models.Index(fields=["whatsapp_number", "is_active"], name="idx_conversation_number_active"),
            models.Index(fields=["whatsapp_number", "last_message_at"], name="idx_conversation_number_last"),
            models.Index(fields=["customer", "last_message_at"], name="idx_conversation_customer_last"),
        ]

    def __str__(self):
        return f"{self.whatsapp_number.phone_number} - {self.customer.phone_number}"


class Message(TemporalMixin, LifeCycleMixin, AuthorMixin):
    """
    DOCSTRING: Message

    Description:
    - Represent a monitored WhatsApp message persisted by CentralChat.
    - Store normalized message information independently from the raw Meta webhook payload.

    Notes:
    - Messages belong to exactly one conversation.
    - meta_message_id provides the primary idempotency key for Meta message persistence.
    - INBOUND represents customer to business.
    - OUTBOUND represents business to customer.
    - text_body may be empty for media, revoke, unsupported, and other non-text messages.
    - Messages must only be persisted when they fall inside the applicable monitoring window.
    - Duplicate Meta webhook deliveries must not create duplicate message records.
    """

    conversation = models.ForeignKey(Conversation, blank=False, null=False, on_delete=models.PROTECT, related_name="messages")
    meta_message_id = models.CharField(max_length=255, blank=False, null=False, unique=True)
    direction = models.CharField(max_length=20, blank=False, null=False, choices=MESSAGE_DIRECTION_REGISTRY.choices)
    message_type = models.CharField(max_length=20, blank=False, null=False, choices=MESSAGE_TYPE_REGISTRY.choices)
    sender_phone_number = models.CharField(max_length=30, blank=False, null=False)
    recipient_phone_number = models.CharField(max_length=30, blank=False, null=False)
    text_body = models.TextField(blank=True, null=False, default="")
    message_timestamp = models.DateTimeField(blank=False, null=False)
    meta_event_timestamp = models.DateTimeField(blank=False, null=False)
    revoked_at = models.DateTimeField(blank=True, null=True)
    edited_message = models.ForeignKey("self", blank=True, null=True, on_delete=models.PROTECT, related_name="edit_events")

    class Meta:
        db_table = "whatsapp_message"
        ordering = ["message_timestamp", "id"]
        indexes = [
            models.Index(fields=["conversation", "message_timestamp"], name="idx_message_conversation_time"),
            models.Index(fields=["direction", "message_timestamp"], name="idx_message_direction_time"),
            models.Index(fields=["message_type", "message_timestamp"], name="idx_message_type_time"),
        ]

    def __str__(self):
        return self.meta_message_id


class MediaAttachment(TemporalMixin, LifeCycleMixin, AuthorMixin):
    """
    DOCSTRING: Media Attachment

    Description:
    - Represent metadata for media attached to a monitored WhatsApp message.
    - Reference privately stored binary content without storing large files directly in PostgreSQL.

    Notes:
    - Binary content must be stored through object storage.
    - storage_key identifies the private object-storage location.
    - Meta media identifiers are used to retrieve supported media from WhatsApp Business Platform.
    - Permanent public media URLs must not be stored.
    """

    message = models.ForeignKey(Message, blank=False, null=False, on_delete=models.PROTECT, related_name="media_attachments")
    meta_media_id = models.CharField(max_length=255, blank=False, null=False)
    storage_key = models.CharField(max_length=500, blank=True, null=False, default="")
    mime_type = models.CharField(max_length=150, blank=False, null=False)
    size = models.BigIntegerField(blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True, null=False, default="")
    checksum = models.CharField(max_length=255, blank=True, null=False, default="")
    is_stored = models.BooleanField(default=False)

    class Meta:
        db_table = "whatsapp_media_attachment"
        indexes = [
            models.Index(fields=["message", "is_active"], name="idx_media_message_active"),
            models.Index(fields=["meta_media_id"], name="idx_media_meta_id"),
            models.Index(fields=["is_stored"], name="idx_media_stored"),
        ]

    def __str__(self):
        return self.original_filename or self.meta_media_id


class ConversationReadState(TemporalMixin):
    """
    DOCSTRING: Conversation Read State

    Description:
    - Maintain the read and unread state of a conversation independently for each monitoring user.
    - Support WhatsApp-style unread indicators in the conversation list.

    Notes:
    - Read state belongs to a specific user and conversation combination.
    - Opening a conversation marks it as read only for the authenticated monitoring user.
    - A new inbound message marks the conversation as unread for applicable monitoring users.
    - last_read_message identifies the most recent message acknowledged by the monitoring user.
    - unread_count supports displaying an unread message badge without recalculating the complete message history.
    """

    conversation = models.ForeignKey(Conversation, blank=False, null=False, on_delete=models.CASCADE, related_name="read_states")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=False, null=False, on_delete=models.CASCADE, related_name="whatsapp_conversation_read_states")
    is_read = models.BooleanField(default=False)
    unread_count = models.PositiveIntegerField(default=0)
    last_read_message = models.ForeignKey(Message, blank=True, null=True, on_delete=models.SET_NULL, related_name="+")
    last_opened_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "whatsapp_conversation_read_state"
        constraints = [
            models.UniqueConstraint(fields=["conversation", "user"], name="unique_conversation_read_state_per_user"),
        ]
        indexes = [
            models.Index(fields=["user", "is_read"], name="idx_read_state_user_read"),
            models.Index(fields=["conversation", "user"], name="idx_readstate_conv_user"),
        ]

    def __str__(self):
        return f"{self.user_id} - {self.conversation_id}"