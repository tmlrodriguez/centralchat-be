from django.db import transaction
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
        - Create a CentralChat ADMINISTRATOR user.
        - Assign the administrative role exclusively through the backend.
        - Record the creation through the centralized auditing subsystem.

        Notes:
        - The client cannot select or override the ADMINISTRATOR role.
        - Password information must never be included in audit metadata.
        - Administrator creation is executed inside a database transaction.
        - The audit event is persisted only after the surrounding transaction commits successfully.
    """

    user = AccessUser.objects.create_user(
        role=ROLE_REGISTRY.ADMINISTRATOR,
        **validated_data,
    )

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.ACCESS,
        action=AUDIT_ACTION_REGISTRY.CREATE,
        description="Usuario administrador creado en CentralChat.",
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
def create_monitor(validated_data, actor):
    """
        DOCSTRING: Create Monitor

        Description:
        - Create a CentralChat MONITOR user.
        - Assign the monitor role exclusively through the backend.
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
        **validated_data,
    )

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.ACCESS,
        action=AUDIT_ACTION_REGISTRY.CREATE,
        description="Usuario monitor creado en CentralChat.",
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