import hashlib
import mimetypes
import uuid
from pathlib import Path
import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files import File
from django.db import transaction
from django.utils import timezone
from .credentials import get_meta_credentials
from .models import MediaAttachment
from .registry import MEDIA_STORAGE_STATUS_REGISTRY
from .storage import private_whatsapp_media_storage

# Define your media helpers here.

class MetaMediaError(Exception):
    """
        DOCSTRING: Meta Media Error

        Description:
        - Represent a controlled failure while resolving, downloading, validating, or storing WhatsApp media.

        Notes:
        - User-facing API responses must not expose Meta access tokens or internal storage paths.
        - The exception message may be persisted as operational media-storage diagnostics.
    """

    pass


def build_storage_key(attachment, mime_type):
    """
        DOCSTRING: Build Storage Key

        Description:
        - Generate a unique private-storage key for a WhatsApp media attachment.

        Notes:
        - The key includes company and WhatsApp-number boundaries for operational organization.
        - User-provided filenames are never used directly as storage paths.
        - A generated UUID prevents storage collisions.
    """

    extension = ""

    if attachment.original_filename:
        candidate_extension = Path(attachment.original_filename).suffix.lower()

        if candidate_extension and len(candidate_extension) <= 10:
            extension = candidate_extension

    if not extension:
        extension = mimetypes.guess_extension(mime_type or "") or ""

    company_id = attachment.message.conversation.whatsapp_number.company_id
    number_id = attachment.message.conversation.whatsapp_number_id
    message_date = attachment.message.message_timestamp
    filename = f"{uuid.uuid4().hex}{extension}"

    return f"whatsapp/{company_id}/{number_id}/{message_date:%Y/%m}/{filename}"


def get_meta_media_metadata(meta_media_id, access_token):
    """
        DOCSTRING: Get Meta Media Metadata

        Description:
        - Retrieve temporary media-download metadata from Meta using a WhatsApp media identifier.

        Notes:
        - The returned Meta URL is temporary and must never be persisted as a permanent media URL.
        - Authorization uses the Meta access token associated with the owning integration.
        - Non-successful Meta responses are converted into controlled MetaMediaError exceptions.
    """

    graph_api_version = getattr(settings, "CENTRALCHAT_META_GRAPH_API_VERSION", "v24.0")
    request_url = f"https://graph.facebook.com/{graph_api_version}/{meta_media_id}"

    try:
        response = requests.get(request_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=settings.CENTRALCHAT_META_MEDIA_REQUEST_TIMEOUT)
    except requests.RequestException as error:
        raise MetaMediaError("Obtención de medio rechazada: no fue posible consultar los metadatos del archivo en Meta.") from error

    if response.status_code != 200:
        raise MetaMediaError("Obtención de medio rechazada: Meta no permitió obtener los metadatos del archivo.")

    try:
        payload = response.json()
    except ValueError as error:
        raise MetaMediaError("Obtención de medio rechazada: Meta devolvió metadatos inválidos.") from error

    media_url = payload.get("url")

    if not media_url:
        raise MetaMediaError("Obtención de medio rechazada: Meta no proporcionó una URL temporal para el archivo.")

    return {
        "url": media_url,
        "mime_type": payload.get("mime_type") or "",
        "sha256": payload.get("sha256") or "",
        "file_size": payload.get("file_size"),
        "id": payload.get("id") or meta_media_id,
    }


def download_meta_media(media_url, access_token, maximum_size):
    """
        DOCSTRING: Download Meta Media

        Description:
        - Download a WhatsApp media binary from the temporary Meta media URL.
        - Calculate the binary size and SHA-256 checksum while streaming the response.

        Notes:
        - The access token is supplied only through the Authorization header.
        - The download is streamed to avoid loading large media files entirely into memory.
        - Files exceeding the configured maximum size are rejected.
    """

    try:
        response = requests.get(media_url, headers={"Authorization": f"Bearer {access_token}"}, stream=True, timeout=settings.CENTRALCHAT_META_MEDIA_REQUEST_TIMEOUT)
    except requests.RequestException as error:
        raise MetaMediaError("Descarga de medio rechazada: no fue posible descargar el archivo desde Meta.") from error

    if response.status_code != 200:
        response.close()
        raise MetaMediaError("Descarga de medio rechazada: Meta no permitió descargar el archivo.")

    temporary_file = settings.CENTRALCHAT_META_MEDIA_TEMPORARY_FILE_CLASS(max_size=settings.CENTRALCHAT_META_MEDIA_MEMORY_THRESHOLD, mode="w+b")
    checksum = hashlib.sha256()
    size = 0

    try:
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue

            size += len(chunk)

            if size > maximum_size:
                raise MetaMediaError("Descarga de medio rechazada: el archivo excede el tamaño máximo permitido.")

            checksum.update(chunk)
            temporary_file.write(chunk)

    except Exception:
        temporary_file.close()
        response.close()
        raise

    response.close()
    temporary_file.seek(0)

    return temporary_file, size, checksum.hexdigest()


def validate_media_metadata(attachment, metadata):
    """
        DOCSTRING: Validate Media Metadata

        Description:
        - Validate Meta media metadata against the CentralChat attachment record and configured media limits.

        Notes:
        - The Meta media identifier must match the attachment identifier.
        - The reported file size must not exceed the configured maximum size.
        - MIME type is synchronized from Meta when available.
    """

    if str(metadata["id"]) != str(attachment.meta_media_id):
        raise MetaMediaError("Obtención de medio rechazada: el identificador del archivo recibido desde Meta no coincide.")

    file_size = metadata.get("file_size")

    if file_size is not None:
        try:
            file_size = int(file_size)
        except (TypeError, ValueError) as error:
            raise MetaMediaError("Obtención de medio rechazada: Meta devolvió un tamaño de archivo inválido.") from error

        if file_size > settings.CENTRALCHAT_META_MEDIA_MAX_SIZE:
            raise MetaMediaError("Obtención de medio rechazada: el archivo excede el tamaño máximo permitido.")


def validate_downloaded_media(metadata, size, checksum):
    """
        DOCSTRING: Validate Downloaded Media

        Description:
        - Validate the downloaded media size and checksum against metadata reported by Meta.

        Notes:
        - Size validation is performed when Meta reports file_size.
        - SHA-256 validation is performed when Meta reports sha256.
        - Validation failures prevent the binary from being persisted.
    """

    reported_size = metadata.get("file_size")

    if reported_size is not None and int(reported_size) != size:
        raise MetaMediaError("Almacenamiento de medio rechazado: el tamaño descargado no coincide con el reportado por Meta.")

    reported_checksum = metadata.get("sha256") or ""

    if reported_checksum and reported_checksum.lower() != checksum.lower():
        raise MetaMediaError("Almacenamiento de medio rechazado: la verificación de integridad SHA-256 falló.")


@transaction.atomic
def store_media_attachment(attachment):
    """
        DOCSTRING: Store Media Attachment

        Description:
        - Retrieve a WhatsApp media binary from Meta and persist it in CentralChat private storage.
        - Validate Meta metadata, file-size limits, and SHA-256 integrity before marking the attachment as stored.

        Notes:
        - The attachment record is locked to prevent concurrent duplicate downloads.
        - Already stored media is returned without downloading again.
        - Failed retrieval attempts remain retryable.
        - Permanent Meta media URLs are never persisted.
    """

    locked_attachment = MediaAttachment.objects.select_for_update().select_related("message__conversation__whatsapp_number__whatsapp_business_account__meta_integration").get(id=attachment.id)

    if locked_attachment.is_stored and locked_attachment.storage_key and private_whatsapp_media_storage.exists(locked_attachment.storage_key):
        return locked_attachment

    locked_attachment.retrieval_attempts += 1
    locked_attachment.storage_error = ""
    locked_attachment.storage_failed_at = None
    locked_attachment.save(update_fields=["retrieval_attempts", "storage_error", "storage_failed_at", "updated_at"])

    integration = locked_attachment.message.conversation.whatsapp_number.whatsapp_business_account.meta_integration

    try:
        credentials = get_meta_credentials(integration.credential_reference)
        metadata = get_meta_media_metadata(meta_media_id=locked_attachment.meta_media_id, access_token=credentials["access_token"])
        validate_media_metadata(attachment=locked_attachment, metadata=metadata)

        temporary_file, size, checksum = download_meta_media(
            media_url=metadata["url"],
            access_token=credentials["access_token"],
            maximum_size=settings.CENTRALCHAT_META_MEDIA_MAX_SIZE,
        )

        try:
            validate_downloaded_media(metadata=metadata, size=size, checksum=checksum)

            mime_type = metadata.get("mime_type") or locked_attachment.mime_type or "application/octet-stream"
            storage_key = build_storage_key(attachment=locked_attachment, mime_type=mime_type)
            saved_storage_key = private_whatsapp_media_storage.save(storage_key, File(temporary_file))
        finally:
            temporary_file.close()

        locked_attachment.storage_key = saved_storage_key
        locked_attachment.storage_status = MEDIA_STORAGE_STATUS_REGISTRY.STORED
        locked_attachment.mime_type = mime_type
        locked_attachment.size = size
        locked_attachment.checksum = checksum
        locked_attachment.is_stored = True
        locked_attachment.stored_at = timezone.now()
        locked_attachment.storage_failed_at = None
        locked_attachment.storage_error = ""
        locked_attachment.save(update_fields=["storage_key", "storage_status", "mime_type", "size", "checksum", "is_stored", "stored_at", "storage_failed_at", "storage_error", "updated_at"])

        return locked_attachment

    except (MetaMediaError, ImproperlyConfigured) as error:
        locked_attachment.storage_status = MEDIA_STORAGE_STATUS_REGISTRY.FAILED
        locked_attachment.is_stored = False
        locked_attachment.storage_failed_at = timezone.now()
        locked_attachment.storage_error = str(error)
        locked_attachment.save(update_fields=["storage_status", "is_stored", "storage_failed_at", "storage_error", "updated_at"])
        raise