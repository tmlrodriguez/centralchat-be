import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from .credentials import get_meta_credentials

# Define your meta lifecycle operations.

class MetaLifecycleAPIError(Exception):
    """
        DOCSTRING: Meta Lifecycle API Error

        Description:
        - Represent a Meta Graph API failure occurring during integration lifecycle validation.

        Notes:
        - Sensitive access tokens are never included in the exception.
        - Meta HTTP status, error code, error subcode, and readable message are preserved for controlled API responses.
    """

    def __init__(self, message, http_status=None, meta_error_code=None, meta_error_subcode=None):
        self.error_message = message
        self.http_status = http_status
        self.meta_error_code = meta_error_code
        self.meta_error_subcode = meta_error_subcode

        super().__init__(message)


class MetaLifecycleClient:
    """
        DOCSTRING: Meta Lifecycle Client

        Description:
        - Provide Meta Graph API operations required to validate and synchronize the CentralChat integration lifecycle.

        Notes:
        - Credentials are resolved from the secure credential store.
        - Access tokens are never persisted in database records.
        - All requests use the Graph API version configured by CentralChat.
        - Lifecycle operations remain independent from message-send and template-management operations.
    """

    def __init__(self, meta_integration):
        self.meta_integration = meta_integration

        credentials = get_meta_credentials(meta_integration.credential_reference)
        self.access_token = credentials.get("access_token")

        if not self.access_token:
            raise ImproperlyConfigured("Configuración de Meta rechazada: el access token no se encuentra configurado.")

        self.graph_api_version = getattr(settings, "CENTRALCHAT_META_GRAPH_API_VERSION", "v26.0")
        self.base_url = f"https://graph.facebook.com/{self.graph_api_version}"

    def _request(self, method, resource_path, params=None, json_payload=None):
        """
            DOCSTRING: Request

            Description:
            - Execute an authenticated Meta Graph API request and normalize lifecycle API failures.

            Notes:
            - Authorization is provided exclusively through the Bearer header.
            - Access tokens are never placed in logs or exception messages.
            - Successful empty Meta responses are normalized to an empty dictionary.
        """

        resource_path = str(resource_path).lstrip("/")
        url = f"{self.base_url}/{resource_path}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                params=params,
                json=json_payload,
                timeout=settings.CENTRALCHAT_META_REQUEST_TIMEOUT,
            )
        except requests.RequestException as error:
            raise MetaLifecycleAPIError("Meta no pudo ser contactado durante la validación de la integración.") from error

        try:
            response_data = response.json() if response.content else {}
        except ValueError as error:
            raise MetaLifecycleAPIError("Meta devolvió una respuesta que no contiene JSON válido.", http_status=response.status_code) from error

        if response.ok:
            return response_data

        error_data = response_data.get("error") if isinstance(response_data, dict) else {}
        error_data = error_data or {}

        raise MetaLifecycleAPIError(
            error_data.get("message") or "Meta rechazó la operación de ciclo de vida.",
            http_status=response.status_code,
            meta_error_code=error_data.get("code"),
            meta_error_subcode=error_data.get("error_subcode"),
        )

    def validate_credentials(self):
        """
            DOCSTRING: Validate Credentials

            Description:
            - Validate that the configured access token is currently accepted by Meta.

            Notes:
            - The authenticated Meta identity is returned for diagnostics.
            - Successful validation does not by itself prove access to a particular WABA.
        """

        return self._request(method="GET", resource_path="me", params={"fields": "id,name"})

    def get_waba(self, meta_waba_id):
        """
            DOCSTRING: Get WABA

            Description:
            - Validate direct access to a WhatsApp Business Account and return its current Meta representation.
        """

        return self._request(method="GET", resource_path=meta_waba_id, params={"fields": "id,name"})

    def list_waba_phone_numbers(self, meta_waba_id):
        """
            DOCSTRING: List WABA Phone Numbers

            Description:
            - Return phone numbers currently associated with a WhatsApp Business Account.

            Notes:
            - This operation is used to prove that a configured Phone Number ID belongs to the expected WABA.
        """

        response_data = self._request(
            method="GET",
            resource_path=f"{meta_waba_id}/phone_numbers",
            params={
                "fields": "id,display_phone_number,verified_name,code_verification_status",
                "limit": 100,
            },
        )

        return response_data.get("data") or []

    def get_phone_number(self, meta_phone_number_id):
        """
            DOCSTRING: Get Phone Number

            Description:
            - Validate direct access to a Meta WhatsApp Phone Number ID.
        """

        return self._request(
            method="GET",
            resource_path=meta_phone_number_id,
            params={"fields": "id,display_phone_number,verified_name,code_verification_status"},
        )

    def list_subscribed_apps(self, meta_waba_id):
        """
            DOCSTRING: List Subscribed Apps

            Description:
            - Return applications currently subscribed to receive webhook events for a WABA.
        """

        response_data = self._request(method="GET", resource_path=f"{meta_waba_id}/subscribed_apps")

        return response_data.get("data") or []

    def subscribe_waba(self, meta_waba_id):
        """
            DOCSTRING: Subscribe WABA

            Description:
            - Subscribe the current Meta application to webhook events for the supplied WABA.
        """

        return self._request(method="POST", resource_path=f"{meta_waba_id}/subscribed_apps")

    def unsubscribe_waba(self, meta_waba_id):
        """
            DOCSTRING: Unsubscribe WABA

            Description:
            - Remove the current Meta application subscription from the supplied WABA.

            Notes:
            - This operation is intentionally explicit because it modifies actual Meta configuration.
        """

        return self._request(method="DELETE", resource_path=f"{meta_waba_id}/subscribed_apps")


def payload_contains_meta_id(payload, expected_id):
    """
        DOCSTRING: Payload Contains Meta ID

        Description:
        - Determine whether an arbitrary Meta response structure contains a particular object identifier.

        Notes:
        - Subscription responses may evolve structurally between Graph API versions.
        - Only exact string identifier matches are accepted.
    """

    expected_id = str(expected_id)

    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "id" and str(value) == expected_id:
                return True

            if payload_contains_meta_id(value, expected_id):
                return True

        return False

    if isinstance(payload, list):
        return any(payload_contains_meta_id(value, expected_id) for value in payload)

    return False