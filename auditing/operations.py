from copy import deepcopy
from django.db import transaction
from .context import get_audit_request_context
from .models import AuditEvent
from .registry import AUDIT_SEVERITY_REGISTRY


# Define your auditing operations here.

SENSITIVE_METADATA_KEYS = {
    "password",
    "password1",
    "password2",
    "token",
    "access_token",
    "refresh_token",
    "api_token",
    "authorization",
    "authorization_header",
    "secret",
    "app_secret",
    "client_secret",
    "verify_token",
    "credential",
    "credentials",
    "credential_reference",
    "cookie",
    "cookies",
    "session",
    "sessionid",
    "csrf",
    "csrf_token",
}


def sanitize_audit_metadata(value):
    """
        DOCSTRING: Sanitize Audit Metadata

        Description:
        - Remove sensitive values recursively from audit metadata before persistence.

        Notes:
        - Dictionary keys are compared case-insensitively.
        - Sensitive values are replaced instead of persisted.
        - Lists and nested dictionaries are sanitized recursively.
        - Primitive non-sensitive values remain unchanged.
    """

    if isinstance(value, dict):
        sanitized = {}

        for key, item in value.items():
            normalized_key = str(key).strip().lower()

            if normalized_key in SENSITIVE_METADATA_KEYS:
                sanitized[key] = "[REDACTED]"
                continue

            sanitized[key] = sanitize_audit_metadata(item)

        return sanitized

    if isinstance(value, list):
        return [sanitize_audit_metadata(item) for item in value]

    if isinstance(value, tuple):
        return [sanitize_audit_metadata(item) for item in value]

    return value


def resolve_audit_target(target):
    """
        DOCSTRING: Resolve Audit Target

        Description:
        - Normalize a Django model instance into audit target identity fields.

        Notes:
        - Missing targets produce empty target identity.
        - Model metadata is used instead of Python module paths so target identity remains stable.
    """

    if target is None:
        return {
            "target_app": "",
            "target_model": "",
            "target_id": "",
            "target_label": "",
        }

    model_meta = getattr(target, "_meta", None)

    if model_meta is None:
        return {
            "target_app": "",
            "target_model": target.__class__.__name__,
            "target_id": str(getattr(target, "pk", "") or ""),
            "target_label": str(target),
        }

    return {
        "target_app": model_meta.app_label,
        "target_model": model_meta.model_name,
        "target_id": str(getattr(target, "pk", "") or ""),
        "target_label": str(target),
    }


def record_audit_event(
    category,
    action,
    description,
    actor=None,
    company=None,
    branch=None,
    target=None,
    metadata=None,
    severity=AUDIT_SEVERITY_REGISTRY.INFO,
    request_id=None,
    ip_address=None,
    user_agent=None,
):
    """
        DOCSTRING: Record Audit Event

        Description:
        - Persist one immutable Dialoqo audit event.

        Notes:
        - Request metadata is automatically resolved from the current auditing context when explicit values are not supplied.
        - Sensitive metadata values are sanitized before persistence.
        - target may be any Django model instance.
        - The operation may also be used by background tasks with actor=None.
    """

    request_context = get_audit_request_context()
    target_data = resolve_audit_target(target)
    sanitized_metadata = sanitize_audit_metadata(deepcopy(metadata or {}))

    resolved_request_id = request_id if request_id is not None else request_context.get("request_id", "")
    resolved_ip_address = ip_address if ip_address is not None else request_context.get("ip_address") or None
    resolved_user_agent = user_agent if user_agent is not None else request_context.get("user_agent", "")

    return AuditEvent.objects.create(
        company=company,
        branch=branch,
        actor=actor,
        category=category,
        action=action,
        severity=severity,
        target_app=target_data["target_app"],
        target_model=target_data["target_model"],
        target_id=target_data["target_id"],
        target_label=target_data["target_label"],
        description=description,
        metadata=sanitized_metadata,
        request_id=resolved_request_id,
        ip_address=resolved_ip_address,
        user_agent=resolved_user_agent,
    )


def schedule_audit_event(
    category,
    action,
    description,
    actor=None,
    company=None,
    branch=None,
    target=None,
    metadata=None,
    severity=AUDIT_SEVERITY_REGISTRY.INFO,
):
    """
        DOCSTRING: Schedule Audit Event

        Description:
        - Schedule an audit event for persistence only after the surrounding database transaction commits successfully.

        Notes:
        - Successful-operation audit records must not survive rolled-back business transactions.
        - Request metadata is captured before transaction commit so ASGI request context remains available.
        - Target identity is captured before transaction commit so mutable model instances are not required later.
    """

    request_context = get_audit_request_context()
    target_data = resolve_audit_target(target)
    sanitized_metadata = sanitize_audit_metadata(deepcopy(metadata or {}))

    company_id = company.id if company else None
    branch_id = branch.id if branch else None
    actor_id = actor.id if actor else None

    def publish():
        AuditEvent.objects.create(
            company_id=company_id,
            branch_id=branch_id,
            actor_id=actor_id,
            category=category,
            action=action,
            severity=severity,
            target_app=target_data["target_app"],
            target_model=target_data["target_model"],
            target_id=target_data["target_id"],
            target_label=target_data["target_label"],
            description=description,
            metadata=sanitized_metadata,
            request_id=request_context.get("request_id", ""),
            ip_address=request_context.get("ip_address") or None,
            user_agent=request_context.get("user_agent", ""),
        )

    transaction.on_commit(publish)