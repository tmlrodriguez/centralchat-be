from django.db import models

# Define your registries here.

class MESSAGE_DIRECTION_REGISTRY(models.TextChoices):
    """
        DOCSTRING: Message Direction Registry

        Description:
        - Define the supported direction values for monitored WhatsApp messages.
        - Distinguish messages received by the business from messages sent by the business.

        Notes:
        - INBOUND represents messages sent from an external WhatsApp customer to a company-owned WhatsApp number.
        - OUTBOUND represents messages sent from a company-owned WhatsApp number to an external WhatsApp customer.
        - Registry values are persisted directly in the Message model.
    """

    INBOUND = "INBOUND", "Inbound"
    OUTBOUND = "OUTBOUND", "Outbound"


class MESSAGE_TYPE_REGISTRY(models.TextChoices):
    """
        DOCSTRING: Message Type Registry

        Description:
        - Define the normalized WhatsApp message types supported by Dialoqo.
        - Provide stable internal values independently from the raw Meta webhook payload structure.

        Notes:
        - TEXT represents standard text messages.
        - IMAGE, AUDIO, VIDEO, DOCUMENT, and STICKER represent media-based messages.
        - LOCATION represents geographic location messages.
        - CONTACTS represents shared contact information.
        - INTERACTIVE represents interactive WhatsApp message payloads.
        - TEMPLATE represents WhatsApp message template content.
        - REACTION represents emoji reactions associated with WhatsApp messages.
        - BUTTON represents button response messages.
        - ORDER represents commerce-related order messages.
        - UNSUPPORTED preserves messages whose Meta type is not yet explicitly supported by Dialoqo.
        - Registry values are persisted directly in the Message model.
    """

    TEXT = "TEXT", "Text"
    IMAGE = "IMAGE", "Image"
    AUDIO = "AUDIO", "Audio"
    VIDEO = "VIDEO", "Video"
    DOCUMENT = "DOCUMENT", "Document"
    STICKER = "STICKER", "Sticker"
    LOCATION = "LOCATION", "Location"
    CONTACTS = "CONTACTS", "Contacts"
    INTERACTIVE = "INTERACTIVE", "Interactive"
    TEMPLATE = "TEMPLATE", "Template"
    REACTION = "REACTION", "Reaction"
    BUTTON = "BUTTON", "Button"
    ORDER = "ORDER", "Order"
    UNSUPPORTED = "UNSUPPORTED", "Unsupported"


class MESSAGE_STATUS_REGISTRY(models.TextChoices):
    """
        DOCSTRING: Message Status Registry

        Description:
        - Define the normalized lifecycle states supported for monitored WhatsApp messages.
        - Represent inbound reception state and outbound Meta delivery progression.

        Notes:
        - RECEIVED represents an inbound message successfully received and persisted by Dialoqo.
        - PENDING represents an outbound message created locally before Meta confirms transmission.
        - SENT represents an outbound message accepted and reported as sent by Meta.
        - DELIVERED represents an outbound message delivered to the recipient.
        - READ represents an outbound message reported as read by the recipient.
        - FAILED represents an outbound message whose delivery failed.
        - Outbound delivery states must not regress when delayed or out-of-order Meta webhook events are received.
        - Registry values are persisted directly in the Message model.
    """

    RECEIVED = "RECEIVED", "Received"
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    DELIVERED = "DELIVERED", "Delivered"
    READ = "READ", "Read"
    FAILED = "FAILED", "Failed"


class MEDIA_STORAGE_STATUS_REGISTRY(models.TextChoices):
    """
        DOCSTRING: Media Storage Status Registry

        Description:
        - Define the private-storage lifecycle states supported for WhatsApp media attachments.
        - Distinguish media awaiting retrieval from successfully stored and failed media.

        Notes:
        - PENDING represents media metadata that has been persisted but whose binary has not yet been stored.
        - STORED represents media whose binary content is available in Dialoqo private storage.
        - FAILED represents a media retrieval or validation attempt that could not be completed successfully.
        - A FAILED attachment may be retried because Meta media retrieval failures can be temporary.
        - Registry values are persisted directly in the MediaAttachment model.
    """

    PENDING = "PENDING", "Pending"
    STORED = "STORED", "Stored"
    FAILED = "FAILED", "Failed"


class MESSAGE_TEMPLATE_STATUS_REGISTRY(models.TextChoices):
    """
        DOCSTRING: Message Template Status Registry

        Description:
        - Define the normalized lifecycle states supported for WhatsApp message templates.
        - Mirror the operational approval state reported by Meta.

        Notes:
        - APPROVED templates may be used for outbound template messaging.
        - PENDING templates remain under Meta review.
        - REJECTED templates cannot be used for outbound messaging.
        - PAUSED and DISABLED templates are unavailable for new outbound delivery.
        - PENDING_DELETION represents templates awaiting permanent deletion.
        - IN_APPEAL represents templates whose rejection or restriction is under appeal.
        - UNKNOWN preserves Meta states not yet explicitly mapped by Dialoqo.
    """

    APPROVED = "APPROVED", "Approved"
    PENDING = "PENDING", "Pending"
    REJECTED = "REJECTED", "Rejected"
    PAUSED = "PAUSED", "Paused"
    DISABLED = "DISABLED", "Disabled"
    PENDING_DELETION = "PENDING_DELETION", "Pending Deletion"
    IN_APPEAL = "IN_APPEAL", "In Appeal"
    UNKNOWN = "UNKNOWN", "Unknown"


class MESSAGE_TEMPLATE_CATEGORY_REGISTRY(models.TextChoices):
    """
        DOCSTRING: Message Template Category Registry

        Description:
        - Define the WhatsApp template categories supported by Dialoqo.

        Notes:
        - MARKETING represents promotional and engagement communication.
        - UTILITY represents transactional and operational communication.
        - AUTHENTICATION represents identity-verification communication.
        - UNKNOWN preserves categories not yet explicitly supported by Dialoqo.
    """

    MARKETING = "MARKETING", "Marketing"
    UTILITY = "UTILITY", "Utility"
    AUTHENTICATION = "AUTHENTICATION", "Authentication"
    UNKNOWN = "UNKNOWN", "Unknown"


class MESSAGE_TEMPLATE_PARAMETER_FORMAT_REGISTRY(models.TextChoices):
    """
        DOCSTRING: Message Template Parameter Format Registry

        Description:
        - Define how variable placeholders inside WhatsApp templates are identified.

        Notes:
        - POSITIONAL templates use placeholders such as {{1}}, {{2}}, and {{3}}.
        - NAMED templates use named placeholders supplied by Meta.
        - The format is persisted so Dialoqo can validate outbound template parameters before calling Meta.
    """

    POSITIONAL = "POSITIONAL", "Positional"
    NAMED = "NAMED", "Named"


class REALTIME_EVENT_REGISTRY(models.TextChoices):
    """
        DOCSTRING: Realtime Event Registry

        Description:
        - Define the stable realtime event names emitted by the Dialoqo WhatsApp backend.
        - Provide a consistent contract between backend WebSocket publishers and frontend consumers.

        Notes:
        - MESSAGE_CREATED represents a newly persisted inbound or outbound message.
        - MESSAGE_UPDATED represents an existing message whose visible content changed through an edit or revocation.
        - MESSAGE_STATUS_CHANGED represents an outbound delivery lifecycle transition.
        - CONVERSATION_UPDATED represents changes affecting conversation previews or ordering.
        - CONVERSATION_READ_STATE_CHANGED represents a monitor-specific read-state update.
        - NUMBER_ASSIGNMENT_CHANGED represents assignment or unassignment of a WhatsApp number.
        - Registry values are transport-level event identifiers and are not persisted in database models.
    """

    MESSAGE_CREATED = "message.created", "Message Created"
    MESSAGE_UPDATED = "message.updated", "Message Updated"
    MESSAGE_STATUS_CHANGED = "message.status_changed", "Message Status Changed"
    CONVERSATION_UPDATED = "conversation.updated", "Conversation Updated"
    CONVERSATION_READ_STATE_CHANGED = "conversation.read_state_changed", "Conversation Read State Changed"
    NUMBER_ASSIGNMENT_CHANGED = "number.assignment_changed", "Number Assignment Changed"