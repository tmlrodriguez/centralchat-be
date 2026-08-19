from django.db import models


class MESSAGE_DIRECTION_REGISTRY(models.TextChoices):
    """
    DOCSTRING: Message Direction Registry

    Description:
    - Define the supported message directions used by CentralChat.

    Notes:
    - INBOUND represents messages sent from the customer to the corporate WhatsApp number.
    - OUTBOUND represents messages sent from the company member to the customer.
    """

    INBOUND = "INBOUND", "Inbound"
    OUTBOUND = "OUTBOUND", "Outbound"


class MESSAGE_TYPE_REGISTRY(models.TextChoices):
    """
    DOCSTRING: Message Type Registry

    Description:
    - Define the supported WhatsApp message types persisted by CentralChat.

    Notes:
    - Message type does not imply that text content is available.
    - Unsupported Meta message types must be handled without corrupting message processing.
    """

    TEXT = "TEXT", "Text"
    IMAGE = "IMAGE", "Image"
    AUDIO = "AUDIO", "Audio"
    VIDEO = "VIDEO", "Video"
    DOCUMENT = "DOCUMENT", "Document"
    STICKER = "STICKER", "Sticker"
    EDIT = "EDIT", "Edit"
    REVOKE = "REVOKE", "Revoke"
    UNSUPPORTED = "UNSUPPORTED", "Unsupported"