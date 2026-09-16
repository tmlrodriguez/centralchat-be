from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.utils import timezone
from auditing.operations import schedule_audit_event
from auditing.registry import AUDIT_ACTION_REGISTRY, AUDIT_CATEGORY_REGISTRY
from .credentials import get_meta_app_id
from .meta_lifecycle import MetaLifecycleAPIError, MetaLifecycleClient, payload_contains_meta_id
from .models import WhatsAppBusinessAccount, WhatsAppNumber
from .webhook import normalize_phone_number

# Define your Meta lifecycle operations here.

def validate_phone_number_identity(whatsapp_number, meta_phone_data):
    """
        DOCSTRING: Validate Phone Number Identity

        Description:
        - Validate that the phone number returned by Meta matches the corporate number configured in Dialoqo.

        Notes:
        - Comparison ignores formatting characters and leading plus signs.
        - A mismatched phone number causes the local connection state to be rejected.
    """

    meta_display_phone_number = meta_phone_data.get("display_phone_number") or ""
    configured_phone_number = whatsapp_number.phone_number

    if normalize_phone_number(meta_display_phone_number) != normalize_phone_number(configured_phone_number):
        raise ValidationError({"meta_phone_number_id": "Validación de número rechazada: el Phone Number ID corresponde a un número diferente al configurado."})

    return meta_phone_data


def find_waba_phone_number(waba_phone_numbers, meta_phone_number_id):
    """
        DOCSTRING: Find WABA Phone Number

        Description:
        - Resolve a Phone Number ID from the collection returned by the configured WABA.

        Notes:
        - Returning None means the Phone Number ID does not belong to that WABA.
    """

    expected_id = str(meta_phone_number_id)

    for phone_data in waba_phone_numbers:
        if str(phone_data.get("id")) == expected_id:
            return phone_data

    return None


def validate_whatsapp_number_connection(whatsapp_number, actor, client=None, audit_event=True):
    """
        DOCSTRING: Validate WhatsApp Number Connection

        Description:
        - Validate that a configured Meta Phone Number ID exists, is accessible, belongs to the expected WABA, and matches the configured corporate phone number.
        - Synchronize WhatsAppNumber.is_connected from actual Meta state.
        - Record successful explicit number validation in the centralized audit subsystem.

        Notes:
        - Direct Phone Number ID access alone is insufficient.
        - Membership in the configured WABA is verified independently.
        - Meta API calls are executed before acquiring database row locks.
        - Database row locks are acquired only while persisting connection state.
        - Failed validation persists the disconnected state before propagating the validation error.
        - audit_event may be disabled when this operation is executed internally by a broader lifecycle operation.
        - Sensitive Meta credentials are never copied into audit metadata.
    """

    current_number = WhatsAppNumber.objects.select_related(
        "company",
        "branch",
        "whatsapp_business_account",
    ).get(id=whatsapp_number.id)

    account = current_number.whatsapp_business_account

    if current_number.company_id != account.company_id:
        raise ValidationError({
            "whatsapp_number": "Validación de número rechazada: la jerarquía de empresa y WABA no es consistente."
        })

    if client is None:
        client = MetaLifecycleClient()

    try:
        waba_phone_numbers = client.list_waba_phone_numbers(account.meta_waba_id)

        waba_phone_data = find_waba_phone_number(
            waba_phone_numbers=waba_phone_numbers,
            meta_phone_number_id=current_number.meta_phone_number_id,
        )

        if waba_phone_data is None:
            raise ValidationError({
                "meta_phone_number_id": "Validación de número rechazada: el Phone Number ID no pertenece a la cuenta de WhatsApp Business configurada."
            })

        meta_phone_data = client.get_phone_number(
            current_number.meta_phone_number_id
        )

        if str(meta_phone_data.get("id")) != str(current_number.meta_phone_number_id):
            raise ValidationError({
                "meta_phone_number_id": "Validación de número rechazada: Meta devolvió un Phone Number ID diferente al configurado."
            })

        validate_phone_number_identity(
            whatsapp_number=current_number,
            meta_phone_data=meta_phone_data,
        )

    except (MetaLifecycleAPIError, ValidationError):
        with transaction.atomic():
            locked_number = WhatsAppNumber.objects.select_for_update().get(
                id=current_number.id
            )

            locked_number.is_connected = False
            locked_number.updated_by = actor
            locked_number.save(
                update_fields=[
                    "is_connected",
                    "updated_by",
                    "updated_at",
                ]
            )

        raise

    with transaction.atomic():
        locked_number = WhatsAppNumber.objects.select_for_update().select_related(
            "company",
            "branch",
            "whatsapp_business_account",
        ).get(id=current_number.id)

        locked_number.is_connected = True
        locked_number.updated_by = actor
        locked_number.save(
            update_fields=[
                "is_connected",
                "updated_by",
                "updated_at",
            ]
        )

        if audit_event:
            schedule_audit_event(
                category=AUDIT_CATEGORY_REGISTRY.META,
                action=AUDIT_ACTION_REGISTRY.VALIDATE,
                description="Número de WhatsApp validado correctamente contra Meta.",
                actor=actor,
                company=locked_number.company,
                branch=locked_number.branch,
                target=locked_number,
                metadata={
                    "whatsapp_number_id": locked_number.id,
                    "whatsapp_business_account_id": locked_number.whatsapp_business_account_id,
                    "meta_waba_id": locked_number.whatsapp_business_account.meta_waba_id,
                    "meta_phone_number_id": locked_number.meta_phone_number_id,
                    "is_connected": locked_number.is_connected,
                    "verified_name": meta_phone_data.get("verified_name") or "",
                    "code_verification_status": meta_phone_data.get("code_verification_status") or "",
                },
            )

    return {
        "whatsapp_number": locked_number,
        "meta_phone": meta_phone_data,
    }


@transaction.atomic
def refresh_whatsapp_business_account_state(whatsapp_business_account, actor, audit_event=True):
    """
        DOCSTRING: Refresh WhatsApp Business Account State

        Description:
        - Read the actual Meta state of a configured WABA without modifying the external subscription.
        - Synchronize WABA and associated phone-number connection flags.
        - Record explicit lifecycle synchronization in the centralized audit subsystem.

        Notes:
        - is_connected reflects successful WABA access.
        - is_webhook_configured reflects whether the configured Meta app is actually subscribed to the WABA.
        - Every active Dialoqo WhatsApp number belonging to the WABA is independently validated.
        - Internal number validation does not generate individual audit events during a WABA refresh.
        - audit_event may be disabled when this operation is executed as part of a broader connection workflow.
    """

    account = WhatsAppBusinessAccount.objects.select_for_update().select_related("company").get(id=whatsapp_business_account.id)


    client = MetaLifecycleClient()

    try:
        client.validate_credentials()

        meta_waba = client.get_waba(account.meta_waba_id)

        if str(meta_waba.get("id")) != str(account.meta_waba_id):
            raise ValidationError({"meta_waba_id": "Validación de cuenta rechazada: Meta devolvió una WABA diferente a la configurada."})

        subscribed_apps = client.list_subscribed_apps(account.meta_waba_id)
        webhook_configured = payload_contains_meta_id(subscribed_apps, get_meta_app_id())

    except (MetaLifecycleAPIError, ValidationError):
        now = timezone.now()


        account.is_connected = False
        account.is_webhook_configured = False
        account.disconnected_at = now
        account.updated_by = actor
        account.save(update_fields=["is_connected", "is_webhook_configured", "disconnected_at", "updated_by", "updated_at"])

        account.numbers.filter(is_active=True).update(is_connected=False, updated_at=now)

        raise

    now = timezone.now()


    account.is_connected = True
    account.is_webhook_configured = webhook_configured
    account.connected_at = account.connected_at or now
    account.disconnected_at = None
    account.updated_by = actor
    account.save(update_fields=["is_connected", "is_webhook_configured", "connected_at", "disconnected_at", "updated_by", "updated_at"])

    number_results = []
    numbers = account.numbers.filter(is_active=True).order_by("id")

    for number in numbers:
        try:
            result = validate_whatsapp_number_connection(
                whatsapp_number=number,
                actor=actor,
                client=client,
                audit_event=False,
            )

            number_results.append(
                {
                    "id": number.id,
                    "connected": True,
                    "meta_phone": result["meta_phone"],
                }
            )

        except (ValidationError, MetaLifecycleAPIError) as error:
            number_results.append(
                {
                    "id": number.id,
                    "connected": False,
                    "error": str(error),
                }
            )

    if audit_event:
        schedule_audit_event(
            category=AUDIT_CATEGORY_REGISTRY.META,
            action=AUDIT_ACTION_REGISTRY.SYNCHRONIZE,
            description="Estado de cuenta de WhatsApp Business sincronizado con Meta.",
            actor=actor,
            company=account.company,
            target=account,
            metadata={
                "whatsapp_business_account_id": account.id,
                "meta_waba_id": account.meta_waba_id,
                "is_connected": account.is_connected,
                "is_webhook_configured": account.is_webhook_configured,
                "validated_numbers": len(number_results),
                "connected_numbers": len([result for result in number_results if result["connected"]]),
                "disconnected_numbers": len([result for result in number_results if not result["connected"]]),
            },
        )

    return {
        "whatsapp_business_account": account,
        "meta_waba": meta_waba,
        "subscribed_apps": subscribed_apps,
        "numbers": number_results,
    }


@transaction.atomic
def connect_whatsapp_business_account(whatsapp_business_account, actor):
    """
        DOCSTRING: Connect WhatsApp Business Account

        Description:
        - Validate Meta credentials and WABA access.
        - Subscribe the configured Meta app to the WABA.
        - Verify the resulting subscription.
        - Synchronize WABA and phone-number lifecycle state.
        - Record the successful connection in the centralized audit subsystem.

        Notes:
        - is_webhook_configured becomes True only after Meta reports the app as subscribed.
        - A successful POST response alone is not trusted; the subscription is read back from Meta.
        - Internal lifecycle synchronization does not generate a duplicate SYNCHRONIZE audit event.
        - Internal phone-number validation does not generate duplicate VALIDATE audit events.
    """

    account = WhatsAppBusinessAccount.objects.select_for_update().select_related("company").get(id=whatsapp_business_account.id)
    client = MetaLifecycleClient()

    client.validate_credentials()

    meta_waba = client.get_waba(account.meta_waba_id)

    if str(meta_waba.get("id")) != str(account.meta_waba_id):
        raise ValidationError({"meta_waba_id": "Conexión de cuenta rechazada: Meta devolvió una WABA diferente a la configurada."})

    client.subscribe_waba(account.meta_waba_id)

    subscribed_apps = client.list_subscribed_apps(account.meta_waba_id)

    if not payload_contains_meta_id(subscribed_apps, get_meta_app_id()):
        raise ValidationError({"webhook": "Conexión de cuenta rechazada: Meta no confirmó la suscripción de la aplicación a la WABA."})

    result = refresh_whatsapp_business_account_state(
        whatsapp_business_account=account,
        actor=actor,
        audit_event=False,
    )

    synchronized_account = result["whatsapp_business_account"]

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.META,
        action=AUDIT_ACTION_REGISTRY.CONNECT,
        description="Cuenta de WhatsApp Business conectada correctamente con Meta.",
        actor=actor,
        company=synchronized_account.company,
        target=synchronized_account,
        metadata={
            "whatsapp_business_account_id": synchronized_account.id,
            "meta_app_id": get_meta_app_id(),
            "meta_waba_id": synchronized_account.meta_waba_id,
            "is_connected": synchronized_account.is_connected,
            "is_webhook_configured": synchronized_account.is_webhook_configured,
            "validated_numbers": len(result["numbers"]),
            "connected_numbers": len([number for number in result["numbers"] if number["connected"]]),
            "disconnected_numbers": len([number for number in result["numbers"] if not number["connected"]]),
        },
    )

    return result


@transaction.atomic
def disconnect_whatsapp_business_account(whatsapp_business_account, actor):
    """
        DOCSTRING: Disconnect WhatsApp Business Account

        Description:
        - Remove the current application's WABA subscription from Meta.
        - Verify the actual subscription state after removal.
        - Synchronize local lifecycle fields.
        - Record the successful disconnection in the centralized audit subsystem.

        Notes:
        - This operation modifies external Meta configuration.
        - Existing monitored conversation history remains preserved.
        - Monitoring should be disabled before disconnecting the WABA.
        - Sensitive Meta credentials are never copied into audit metadata.
        - Audit history is created only after the surrounding transaction commits successfully.
    """

    account = WhatsAppBusinessAccount.objects.select_for_update().select_related("company").get(id=whatsapp_business_account.id)

    if account.numbers.filter(is_active=True, is_monitoring_enabled=True).exists():
        raise ValidationError({"whatsapp_business_account": "Desconexión de cuenta rechazada: existen números con monitoreo activo."})

    client = MetaLifecycleClient()

    client.validate_credentials()
    client.unsubscribe_waba(account.meta_waba_id)

    subscribed_apps = client.list_subscribed_apps(account.meta_waba_id)

    if payload_contains_meta_id(subscribed_apps, get_meta_app_id()):
        raise ValidationError({"webhook": "Desconexión de cuenta rechazada: Meta todavía reporta la aplicación como suscrita a la WABA."})

    now = timezone.now()

    active_number_ids = list(account.numbers.filter(is_active=True).values_list("id", flat=True))

    account.is_connected = False
    account.is_webhook_configured = False
    account.disconnected_at = now
    account.updated_by = actor
    account.save(update_fields=["is_connected", "is_webhook_configured", "disconnected_at", "updated_by", "updated_at"])

    account.numbers.filter(is_active=True).update(is_connected=False, updated_at=now)

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.META,
        action=AUDIT_ACTION_REGISTRY.DISCONNECT,
        description="Cuenta de WhatsApp Business desconectada de Meta.",
        actor=actor,
        company=account.company,
        target=account,
        metadata={
            "whatsapp_business_account_id": account.id,
            "meta_app_id": get_meta_app_id(),
            "meta_waba_id": account.meta_waba_id,
            "is_connected": account.is_connected,
            "is_webhook_configured": account.is_webhook_configured,
            "disconnected_at": account.disconnected_at.isoformat(),
            "disconnected_number_ids": active_number_ids,
        },
    )

    return {
        "whatsapp_business_account": account,
        "subscribed_apps": subscribed_apps,
    }