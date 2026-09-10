from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework.authtoken.models import Token
from auditing.operations import schedule_audit_event
from auditing.registry import AUDIT_ACTION_REGISTRY, AUDIT_CATEGORY_REGISTRY
from .models import AccessUser
from .registry import ROLE_REGISTRY


# Define your access operations here.

@transaction.atomic
def create_administrator(validated_data, actor):
    """
        DOCSTRING: Create Administrator

        Description:
        - Create a Dialoqo ADMINISTRATOR user.
        - Assign the administrative role exclusively through the backend.
        - Preserve the user responsible for creating the administrator.
        - Record the creation through the centralized auditing subsystem.

        Notes:
        - The client cannot select or override the ADMINISTRATOR role.
        - Password information must never be included in audit metadata.
        - Administrator creation is executed inside a database transaction.
        - The audit event is persisted only after the surrounding transaction commits successfully.
    """

    user = AccessUser.objects.create_user(
        role=ROLE_REGISTRY.ADMINISTRATOR,
        created_by=actor,
        updated_by=actor,
        **validated_data,
    )

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.ACCESS,
        action=AUDIT_ACTION_REGISTRY.CREATE,
        description="Usuario administrador creado en Dialoqo.",
        actor=actor,
        target=user,
        metadata={
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_active": user.is_active,
        },
    )

    return user


@transaction.atomic
def update_administrator(administrator, validated_data, actor):
    """
        DOCSTRING: Update Administrator

        Description:
        - Apply validated changes to an existing Dialoqo ADMINISTRATOR user.
        - Record the administrative user change through the centralized auditing subsystem.

        Notes:
        - The user role and ownership relationship cannot be changed through this operation.
        - Password changes are intentionally handled separately.
        - Previous and current non-sensitive values are preserved for audit traceability.
    """

    locked_administrator = AccessUser.objects.select_for_update().get(id=administrator.id)
    changed_fields = list(validated_data.keys())
    previous_values = {field: getattr(locked_administrator, field) for field in changed_fields}

    for field, value in validated_data.items():
        setattr(locked_administrator, field, value)

    locked_administrator.updated_by = actor
    locked_administrator.save(update_fields=[*changed_fields, "updated_by", "updated_at"])

    current_values = {field: getattr(locked_administrator, field) for field in changed_fields}

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.ACCESS,
        action=AUDIT_ACTION_REGISTRY.UPDATE,
        description="Usuario administrador actualizado en Dialoqo.",
        actor=actor,
        target=locked_administrator,
        metadata={
            "user_id": locked_administrator.id,
            "username": locked_administrator.username,
            "role": locked_administrator.role,
            "changed_fields": changed_fields,
            "previous_values": previous_values,
            "current_values": current_values,
        },
    )

    return locked_administrator


@transaction.atomic
def deactivate_administrator(administrator, actor):
    """
        DOCSTRING: Deactivate Administrator

        Description:
        - Deactivate an existing Dialoqo ADMINISTRATOR without deleting historical information.
        - Terminate any active REST authentication token.
        - Record the lifecycle change through the centralized auditing subsystem.

        Notes:
        - Administrator records are never destructively deleted.
        - Existing historical references remain preserved.
        - Authentication tokens are revoked immediately after deactivation.
    """

    locked_administrator = AccessUser.objects.select_for_update().get(id=administrator.id)

    locked_administrator.is_active = False
    locked_administrator.updated_by = actor
    locked_administrator.save(update_fields=["is_active", "updated_by", "updated_at"])

    Token.objects.filter(user=locked_administrator).delete()

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.ACCESS,
        action=AUDIT_ACTION_REGISTRY.DEACTIVATE,
        description="Usuario administrador desactivado en Dialoqo.",
        actor=actor,
        target=locked_administrator,
        metadata={
            "user_id": locked_administrator.id,
            "username": locked_administrator.username,
            "role": locked_administrator.role,
            "is_active": locked_administrator.is_active,
        },
    )

    return locked_administrator


@transaction.atomic
def create_monitor(validated_data, actor):
    """
        DOCSTRING: Create Monitor

        Description:
        - Create a Dialoqo MONITOR user.
        - Assign the monitor role exclusively through the backend.
        - Preserve the administrator responsible for creating the monitor.
        - Record the creation through the centralized auditing subsystem.

        Notes:
        - The client cannot select or override the MONITOR role.
        - Company access is intentionally not created by this operation.
        - Monitor company access is managed independently through the organizations subsystem.
        - Password information must never be included in audit metadata.
        - The audit event is persisted only after the surrounding transaction commits successfully.
    """

    user = AccessUser.objects.create_user(
        role=ROLE_REGISTRY.MONITOR,
        created_by=actor,
        updated_by=actor,
        **validated_data,
    )

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.ACCESS,
        action=AUDIT_ACTION_REGISTRY.CREATE,
        description="Usuario monitor creado en Dialoqo.",
        actor=actor,
        target=user,
        metadata={
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_active": user.is_active,
        },
    )

    return user


@transaction.atomic
def update_monitor(monitor, validated_data, actor):
    """
        DOCSTRING: Update Monitor

        Description:
        - Apply validated changes to an existing Dialoqo MONITOR user.
        - Record the monitor change through the centralized auditing subsystem.

        Notes:
        - The user role and ownership relationship cannot be changed through this operation.
        - Password changes are intentionally handled separately.
        - Existing company access assignments remain unchanged.
    """

    locked_monitor = AccessUser.objects.select_for_update().get(id=monitor.id)
    changed_fields = list(validated_data.keys())
    previous_values = {field: getattr(locked_monitor, field) for field in changed_fields}

    for field, value in validated_data.items():
        setattr(locked_monitor, field, value)

    locked_monitor.updated_by = actor
    locked_monitor.save(update_fields=[*changed_fields, "updated_by", "updated_at"])

    current_values = {field: getattr(locked_monitor, field) for field in changed_fields}

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.ACCESS,
        action=AUDIT_ACTION_REGISTRY.UPDATE,
        description="Usuario monitor actualizado en Dialoqo.",
        actor=actor,
        target=locked_monitor,
        metadata={
            "user_id": locked_monitor.id,
            "username": locked_monitor.username,
            "role": locked_monitor.role,
            "changed_fields": changed_fields,
            "previous_values": previous_values,
            "current_values": current_values,
        },
    )

    return locked_monitor


@transaction.atomic
def deactivate_monitor(monitor, actor):
    """
        DOCSTRING: Deactivate Monitor

        Description:
        - Deactivate an existing Dialoqo MONITOR without deleting historical information.
        - Terminate any active REST authentication token.
        - Record the lifecycle change through the centralized auditing subsystem.

        Notes:
        - Monitor records are never destructively deleted.
        - Existing company-access history remains preserved.
        - An inactive monitor cannot authenticate even if historical access records remain.
        - Authentication tokens are revoked immediately after deactivation.
    """

    locked_monitor = AccessUser.objects.select_for_update().get(id=monitor.id)

    locked_monitor.is_active = False
    locked_monitor.updated_by = actor
    locked_monitor.save(update_fields=["is_active", "updated_by", "updated_at"])

    Token.objects.filter(user=locked_monitor).delete()

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.ACCESS,
        action=AUDIT_ACTION_REGISTRY.DEACTIVATE,
        description="Usuario monitor desactivado en Dialoqo.",
        actor=actor,
        target=locked_monitor,
        metadata={
            "user_id": locked_monitor.id,
            "username": locked_monitor.username,
            "role": locked_monitor.role,
            "is_active": locked_monitor.is_active,
        },
    )

    return locked_monitor