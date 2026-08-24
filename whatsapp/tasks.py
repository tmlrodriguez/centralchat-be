import logging
from celery import shared_task
from django.db import DatabaseError
from .media import MetaMediaError, store_media_attachment
from .models import MediaAttachment, MetaIntegration
from .operations import persist_whatsapp_webhook_payload

logger = logging.getLogger(__name__)


# Define your background tasks here.

@shared_task(bind=True, autoretry_for=(DatabaseError,), retry_backoff=True, retry_backoff_max=60, retry_jitter=True, retry_kwargs={"max_retries": 5}, acks_late=True)
def process_whatsapp_webhook_task(self, meta_integration_id, payload):
    """
        DOCSTRING: Process WhatsApp Webhook Task

        Description:
        - Process a previously authenticated Meta WhatsApp webhook payload in the background.
        - Resolve the Meta integration again inside the Celery worker.
        - Persist messages and delivery-status events through the existing idempotent ingestion operations.

        Notes:
        - Webhook signature verification occurs synchronously before this task is queued.
        - Sensitive Meta credentials are never passed through Redis.
        - Only the integration identifier and validated JSON payload are passed to Celery.
        - Message uniqueness and lifecycle protections provide retry-safe idempotency.
        - Database failures are automatically retried using exponential backoff.
        - Realtime events continue to be emitted through transaction.on_commit after database persistence succeeds.
    """

    integration = MetaIntegration.objects.select_related("company").filter(id=meta_integration_id, company__is_active=True, is_active=True).first()

    if integration is None:
        logger.warning("WhatsApp webhook task ignored: Meta integration %s is unavailable.", meta_integration_id)
        return {"created": 0, "updated": 0, "ignored": 1}

    logger.info("Processing WhatsApp webhook task for Meta integration %s.", integration.id)

    result = persist_whatsapp_webhook_payload(meta_integration=integration, payload=payload)

    logger.info("WhatsApp webhook task completed for Meta integration %s: %s", integration.id, result)

    return result


@shared_task(bind=True, autoretry_for=(DatabaseError,), retry_backoff=True, retry_backoff_max=120, retry_jitter=True, retry_kwargs={"max_retries": 5}, acks_late=True)
def store_whatsapp_media_attachment_task(self, attachment_id):
    """
        DOCSTRING: Store WhatsApp Media Attachment Task

        Description:
        - Retrieve and persist the binary content of a WhatsApp media attachment asynchronously.
        - Reuse the existing private-media storage subsystem.

        Notes:
        - Only the attachment database identifier is sent through the task broker.
        - Sensitive Meta credentials remain resolved internally.
        - Already stored attachments are treated idempotently.
        - Temporary Meta media failures are retried with exponential backoff.
        - Permanently missing attachment records are ignored safely.
    """

    attachment = MediaAttachment.objects.select_related(
        "message",
        "message__conversation",
        "message__conversation__whatsapp_number",
        "message__conversation__whatsapp_number__whatsapp_business_account",
        "message__conversation__whatsapp_number__whatsapp_business_account__meta_integration",
    ).filter(id=attachment_id, is_active=True).first()

    if attachment is None:
        logger.warning("WhatsApp media task ignored: attachment %s is unavailable.", attachment_id)
        return {"stored": False, "ignored": True}

    if attachment.is_stored and attachment.storage_key:
        logger.info("WhatsApp media attachment %s is already stored.", attachment.id)
        return {"stored": True, "ignored": True}

    try:
        attachment = store_media_attachment(attachment)

    except MetaMediaError as error:
        logger.warning("WhatsApp media attachment %s retrieval failed: %s", attachment.id, str(error))
        raise self.retry(exc=error, countdown=min(2 ** self.request.retries, 120), max_retries=5)

    logger.info("WhatsApp media attachment %s stored successfully.", attachment.id)

    return {
        "stored": True,
        "ignored": False,
        "attachment_id": attachment.id,
    }