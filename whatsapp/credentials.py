import json
import os
from django.core.exceptions import ImproperlyConfigured

# Define your helpers here.

def get_meta_credentials(credential_reference):
    """
        DOCSTRING: Get Meta Credentials

        Description:
        - Resolve the Meta credentials associated with a credential reference.

        Notes:
        - Sensitive Meta credentials must remain outside the application database.
        - During development, credentials are resolved from the server environment.
        - Production environments should replace this provider with a dedicated secret-management service.
    """

    secrets_payload = os.environ.get("CENTRALCHAT_META_SECRETS")

    if not secrets_payload:
        raise ImproperlyConfigured("Configuración de Meta rechazada: el almacén de credenciales no se encuentra configurado.")

    try:
        secrets = json.loads(secrets_payload)
    except json.JSONDecodeError as error:
        raise ImproperlyConfigured("Configuración de Meta rechazada: el almacén de credenciales contiene información inválida.") from error

    credentials = secrets.get(credential_reference)

    if credentials is None:
        raise ImproperlyConfigured("Configuración de Meta rechazada: no existen credenciales para la referencia especificada.")

    access_token = credentials.get("access_token")
    app_secret = credentials.get("app_secret")
    verify_token = credentials.get("verify_token")

    if not access_token:
        raise ImproperlyConfigured("Configuración de Meta rechazada: el access token no se encuentra configurado.")

    if not app_secret:
        raise ImproperlyConfigured("Configuración de Meta rechazada: el app secret no se encuentra configurado.")

    if not verify_token:
        raise ImproperlyConfigured("Configuración de Meta rechazada: el verify token no se encuentra configurado.")

    return {
        "access_token": access_token,
        "app_secret": app_secret,
        "verify_token": verify_token,
    }