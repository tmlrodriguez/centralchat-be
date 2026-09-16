import os
from django.core.exceptions import ImproperlyConfigured

# Define your helpers here.


def _get_required_meta_setting(name):
    """
        DOCSTRING: Get Required Meta Setting

        Description:
        - Resolve one required global Dialoqo Meta platform setting from the server environment.

        Notes:
        - Sensitive Meta values remain outside the application database.
        - Environment values are intentionally resolved only on the backend.
    """

    value = os.environ.get(name)

    if not value:
        raise ImproperlyConfigured(f"Configuración de Meta rechazada: {name} no se encuentra configurado.")

    return value


def get_meta_app_id():
    """
        DOCSTRING: Get Meta App ID

        Description:
        - Return the single Meta App ID used globally by the Dialoqo platform.
    """

    return _get_required_meta_setting("DIALOQO_META_APP_ID")


def get_meta_credentials():
    """
        DOCSTRING: Get Meta Credentials

        Description:
        - Resolve the global Meta credentials used by the Dialoqo platform.

        Notes:
        - Dialoqo uses one Meta application across customer companies.
        - Customer administrators never provide or manage application secrets.
        - Sensitive Meta credentials must remain outside the application database.
        - Production environments should preferably inject these values from a dedicated secret-management service.
    """

    return {
        "access_token": _get_required_meta_setting("DIALOQO_META_ACCESS_TOKEN"),
        "app_secret": _get_required_meta_setting("DIALOQO_META_APP_SECRET"),
        "verify_token": _get_required_meta_setting("DIALOQO_META_VERIFY_TOKEN"),
    }
