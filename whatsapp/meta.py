import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from .credentials import get_meta_credentials
from .webhook import normalize_phone_number

# Define your Meta API helpers here.

class MetaWhatsAppAPIError(Exception):
    """
        DOCSTRING: Meta WhatsApp API Error

        Description:
        - Represent a controlled failure returned while communicating with the Meta WhatsApp Cloud API.
        - Preserve safe diagnostic information required by the CentralChat operation layer.

        Notes:
        - Access tokens and sensitive credentials must never appear in the exception.
        - http_status represents the HTTP response received from Meta when available.
        - meta_error_code represents Meta's normalized error code when available.
        - meta_error_subcode represents Meta's normalized error subcode when available.
    """

    def __init__(self, error_message, http_status=None, meta_error_code="", meta_error_subcode=""):
        self.error_message = error_message
        self.http_status = http_status
        self.meta_error_code = str(meta_error_code or "")
        self.meta_error_subcode = str(meta_error_subcode or "")

        super().__init__(error_message)


def get_meta_graph_api_version():
    """
        DOCSTRING: Get Meta Graph API Version

        Description:
        - Resolve the Meta Graph API version used by CentralChat.

        Notes:
        - The version is centralized through Django settings.
    """

    return getattr(settings, "CENTRALCHAT_META_GRAPH_API_VERSION", "v26.0")


def build_meta_graph_api_url(resource_path):
    """
        DOCSTRING: Build Meta Graph API URL

        Description:
        - Build a complete versioned Meta Graph API URL.

        Notes:
        - resource_path contains only the resource portion.
    """

    graph_api_version = get_meta_graph_api_version()
    normalized_resource_path = str(resource_path).lstrip("/")

    return f"https://graph.facebook.com/{graph_api_version}/{normalized_resource_path}"


def extract_meta_api_error(response):
    """
        DOCSTRING: Extract Meta API Error

        Description:
        - Normalize an unsuccessful Meta response.

        Notes:
        - Invalid non-JSON responses are handled safely.
        - Credentials are never exposed.
    """

    try:
        response_data = response.json()
    except ValueError:
        response_data = {}

    error_data = response_data.get("error") or {}

    return MetaWhatsAppAPIError(
        error_message=error_data.get("message") or "Meta rechazó la solicitud de WhatsApp.",
        http_status=response.status_code,
        meta_error_code=error_data.get("code") or "",
        meta_error_subcode=error_data.get("error_subcode") or "",
    )


def get_meta_access_token(meta_integration):
    """
        DOCSTRING: Get Meta Access Token

        Description:
        - Resolve the access token associated with a Meta integration.

        Notes:
        - Credentials remain outside the application database.
        - Configuration failures are converted into MetaWhatsAppAPIError.
    """

    try:
        credentials = get_meta_credentials(meta_integration.credential_reference)
    except ImproperlyConfigured as error:
        raise MetaWhatsAppAPIError(error_message="Operación de Meta rechazada: la integración no se encuentra correctamente configurada.") from error

    return credentials["access_token"]


def meta_get(meta_integration, resource_path, params=None):
    """
        DOCSTRING: Meta Get

        Description:
        - Execute an authenticated GET request against Meta Graph API.

        Notes:
        - Network and API failures are normalized.
    """

    access_token = get_meta_access_token(meta_integration)

    try:
        response = requests.get(
            build_meta_graph_api_url(resource_path),
            headers={"Authorization": f"Bearer {access_token}"},
            params=params or {},
            timeout=20,
        )
    except requests.RequestException as error:
        raise MetaWhatsAppAPIError(error_message="Operación de Meta rechazada: no fue posible comunicarse con Meta.") from error

    if not response.ok:
        raise extract_meta_api_error(response)

    try:
        return response.json()
    except ValueError as error:
        raise MetaWhatsAppAPIError(error_message="Operación de Meta rechazada: Meta devolvió una respuesta inválida.", http_status=response.status_code) from error


def meta_post(meta_integration, resource_path, payload=None, params=None):
    """
        DOCSTRING: Meta Post

        Description:
        - Execute an authenticated POST request against Meta Graph API.

        Notes:
        - Network and API failures are normalized.
    """

    access_token = get_meta_access_token(meta_integration)

    try:
        response = requests.post(
            build_meta_graph_api_url(resource_path),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            params=params or {},
            json=payload or {},
            timeout=20,
        )
    except requests.RequestException as error:
        raise MetaWhatsAppAPIError(error_message="Operación de Meta rechazada: no fue posible comunicarse con Meta.") from error

    if not response.ok:
        raise extract_meta_api_error(response)

    try:
        return response.json()
    except ValueError as error:
        raise MetaWhatsAppAPIError(error_message="Operación de Meta rechazada: Meta devolvió una respuesta inválida.", http_status=response.status_code) from error


def meta_delete(meta_integration, resource_path, params=None):
    """
        DOCSTRING: Meta Delete

        Description:
        - Execute an authenticated DELETE request against Meta Graph API.

        Notes:
        - Network and API failures are normalized.
    """

    access_token = get_meta_access_token(meta_integration)

    try:
        response = requests.delete(
            build_meta_graph_api_url(resource_path),
            headers={"Authorization": f"Bearer {access_token}"},
            params=params or {},
            timeout=20,
        )
    except requests.RequestException as error:
        raise MetaWhatsAppAPIError(error_message="Operación de Meta rechazada: no fue posible comunicarse con Meta.") from error

    if not response.ok:
        raise extract_meta_api_error(response)

    try:
        return response.json()
    except ValueError:
        return {"success": True}


def send_meta_whatsapp_text_message(whatsapp_number, recipient_phone_number, text_body):
    """
        DOCSTRING: Send Meta WhatsApp Text Message

        Description:
        - Send a plain-text WhatsApp message through Meta WhatsApp Cloud API.

        Notes:
        - Transport only.
        - Business validation and persistence belong to the operation layer.
    """

    meta_integration = whatsapp_number.whatsapp_business_account.meta_integration
    normalized_recipient = normalize_phone_number(recipient_phone_number)

    if not normalized_recipient:
        raise MetaWhatsAppAPIError(error_message="Envío de mensaje rechazado: el número de destino no es válido.")

    response_data = meta_post(
        meta_integration=meta_integration,
        resource_path=f"{whatsapp_number.meta_phone_number_id}/messages",
        payload={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalized_recipient,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text_body,
            },
        },
    )

    messages = response_data.get("messages") or []

    if not messages or not messages[0].get("id"):
        raise MetaWhatsAppAPIError(error_message="Envío de mensaje rechazado: Meta no devolvió un identificador de mensaje válido.")

    return {
        "meta_message_id": messages[0]["id"],
        "recipient_phone_number": normalized_recipient,
        "response_data": response_data,
    }


def list_meta_whatsapp_message_templates(whatsapp_business_account):
    """
        DOCSTRING: List Meta WhatsApp Message Templates

        Description:
        - Retrieve all message templates belonging to a WhatsApp Business Account.
        - Follow Meta pagination until the complete template catalog has been retrieved.
        - Return the template representation provided by the Meta Business Management API.

        Notes:
        - The WhatsApp Business Account Meta integration supplies the access token.
        - The default Meta template representation already contains the fields required by CentralChat.
        - Explicit field projection is intentionally avoided because optional template fields may produce Graph API validation failures for some template types.
        - Meta pagination cursors are followed when additional pages are available.
        - Template normalization and persistence remain the responsibility of the synchronization operation.
    """

    meta_integration = whatsapp_business_account.meta_integration
    templates = []
    after = None

    while True:
        params = {"limit": 100}

        if after:
            params["after"] = after

        response_data = meta_get(
            meta_integration=meta_integration,
            resource_path=f"{whatsapp_business_account.meta_waba_id}/message_templates",
            params=params,
        )

        templates.extend(response_data.get("data") or [])

        paging = response_data.get("paging") or {}
        cursors = paging.get("cursors") or {}
        next_url = paging.get("next")
        after = cursors.get("after")

        if not next_url or not after:
            break

    return templates


def create_meta_whatsapp_message_template(whatsapp_business_account, name, language, category, parameter_format, components):
    """
        DOCSTRING: Create Meta WhatsApp Message Template

        Description:
        - Submit a new WhatsApp message template to Meta.

        Notes:
        - Meta performs final template validation and approval review.
        - Newly created templates may remain pending before becoming usable.
    """

    payload = {
        "name": name,
        "language": language,
        "category": category,
        "components": components,
    }

    if parameter_format:
        payload["parameter_format"] = parameter_format

    return meta_post(
        meta_integration=whatsapp_business_account.meta_integration,
        resource_path=f"{whatsapp_business_account.meta_waba_id}/message_templates",
        payload=payload,
    )


def update_meta_whatsapp_message_template(whatsapp_message_template, category=None, components=None):
    """
        DOCSTRING: Update Meta WhatsApp Message Template

        Description:
        - Submit supported message-template modifications to Meta.

        Notes:
        - Meta determines whether a template state permits modification.
        - CentralChat does not locally assume an update succeeded until Meta accepts it.
    """

    payload = {}

    if category is not None:
        payload["category"] = category

    if components is not None:
        payload["components"] = components

    if not payload:
        raise MetaWhatsAppAPIError(error_message="Actualización de plantilla rechazada: no se proporcionaron cambios.")

    return meta_post(
        meta_integration=whatsapp_message_template.whatsapp_business_account.meta_integration,
        resource_path=whatsapp_message_template.meta_template_id,
        payload=payload,
    )


def delete_meta_whatsapp_message_template(whatsapp_message_template):
    """
        DOCSTRING: Delete Meta WhatsApp Message Template

        Description:
        - Request deletion of a WhatsApp message template from Meta.

        Notes:
        - Deletion is addressed through the owning WABA and template name.
        - Local history remains preserved after Meta deletion.
    """

    return meta_delete(
        meta_integration=whatsapp_message_template.whatsapp_business_account.meta_integration,
        resource_path=f"{whatsapp_message_template.whatsapp_business_account.meta_waba_id}/message_templates",
        params={"name": whatsapp_message_template.name},
    )


def send_meta_whatsapp_template_message(whatsapp_number, recipient_phone_number, template_name, language, components=None):
    """
        DOCSTRING: Send Meta WhatsApp Template Message

        Description:
        - Send an approved WhatsApp template message through Meta WhatsApp Cloud API.

        Notes:
        - Recipient phone numbers are normalized before transmission.
        - Template parameters are supplied using Meta component format.
        - Meta returns the authoritative message identifier used for persistence.
    """

    normalized_recipient = normalize_phone_number(recipient_phone_number)

    if not normalized_recipient:
        raise MetaWhatsAppAPIError(error_message="Envío de plantilla rechazado: el número de destino no es válido.")

    template_payload = {
        "name": template_name,
        "language": {
            "code": language,
        },
    }

    if components:
        template_payload["components"] = components

    response_data = meta_post(
        meta_integration=whatsapp_number.whatsapp_business_account.meta_integration,
        resource_path=f"{whatsapp_number.meta_phone_number_id}/messages",
        payload={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalized_recipient,
            "type": "template",
            "template": template_payload,
        },
    )

    messages = response_data.get("messages") or []

    if not messages or not messages[0].get("id"):
        raise MetaWhatsAppAPIError(error_message="Envío de plantilla rechazado: Meta no devolvió un identificador de mensaje válido.")

    return {
        "meta_message_id": messages[0]["id"],
        "recipient_phone_number": normalized_recipient,
        "response_data": response_data,
    }