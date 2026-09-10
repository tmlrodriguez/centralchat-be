from django.core.exceptions import ValidationError
from django.db import transaction

from auditing.operations import schedule_audit_event
from auditing.registry import AUDIT_ACTION_REGISTRY, AUDIT_CATEGORY_REGISTRY

from .models import Member, Position


# Define your member operations here.

@transaction.atomic
def create_position(company, validated_data, actor):
    """
        DOCSTRING: Create Position

        Description:
        - Create an operational position inside a Dialoqo company.
        - Preserve the explicit company tenant boundary.
        - Record the position creation through the centralized auditing subsystem.

        Notes:
        - The company is resolved before this operation is called.
        - The company relationship is controlled exclusively by the backend.
        - The actor is persisted through the author fields.
        - The audit event is persisted only after the surrounding transaction commits successfully.
    """

    position = Position.objects.create(company=company, created_by=actor, updated_by=actor, **validated_data)

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.MEMBER,
        action=AUDIT_ACTION_REGISTRY.CREATE,
        description="Posición creada en Dialoqo.",
        actor=actor,
        company=company,
        target=position,
        metadata={
            "position_id": position.id,
            "company_id": company.id,
            "name": position.name,
            "code": position.code,
            "description": position.description,
            "is_active": position.is_active,
        },
    )

    return position


@transaction.atomic
def update_position(position, validated_data, actor):
    """
        DOCSTRING: Update Position

        Description:
        - Apply validated changes to an existing Dialoqo position.
        - Preserve the position inside its existing company tenant.
        - Record the configuration change through the centralized auditing subsystem.

        Notes:
        - The company relationship cannot be changed through this operation.
        - Previous and current values are preserved for traceability.
        - Only supplied fields are considered changed.
        - The audit event is persisted only after the surrounding transaction commits successfully.
    """

    locked_position = Position.objects.select_for_update().select_related("company").get(id=position.id)

    changed_fields = list(validated_data.keys())

    previous_values = {
        field: getattr(locked_position, field)
        for field in changed_fields
    }

    for field, value in validated_data.items():
        setattr(locked_position, field, value)

    locked_position.updated_by = actor
    locked_position.save()

    current_values = {
        field: getattr(locked_position, field)
        for field in changed_fields
    }

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.MEMBER,
        action=AUDIT_ACTION_REGISTRY.UPDATE,
        description="Posición actualizada en Dialoqo.",
        actor=actor,
        company=locked_position.company,
        target=locked_position,
        metadata={
            "position_id": locked_position.id,
            "company_id": locked_position.company_id,
            "changed_fields": changed_fields,
            "previous_values": previous_values,
            "current_values": current_values,
        },
    )

    return locked_position


@transaction.atomic
def deactivate_position(position, actor):
    """
        DOCSTRING: Deactivate Position

        Description:
        - Deactivate an operational position without deleting its historical record.
        - Record the lifecycle change through the centralized auditing subsystem.

        Notes:
        - Existing historical member relationships remain preserved.
        - The operation is rejected when the position is already inactive.
        - Deactivation does not modify existing member records.
    """

    locked_position = Position.objects.select_for_update().select_related("company").get(id=position.id)

    if not locked_position.is_active:
        raise ValidationError({"position": "Desactivación de posición rechazada: la posición ya se encuentra inactiva."})

    locked_position.is_active = False
    locked_position.updated_by = actor
    locked_position.save(update_fields=["is_active", "updated_by", "updated_at"])

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.MEMBER,
        action=AUDIT_ACTION_REGISTRY.DEACTIVATE,
        description="Posición desactivada en Dialoqo.",
        actor=actor,
        company=locked_position.company,
        target=locked_position,
        metadata={
            "position_id": locked_position.id,
            "company_id": locked_position.company_id,
            "name": locked_position.name,
            "code": locked_position.code,
            "is_active": locked_position.is_active,
        },
    )

    return locked_position


@transaction.atomic
def create_member(company, validated_data, actor):
    """
        DOCSTRING: Create Member

        Description:
        - Create an operational company member inside Dialoqo.
        - Associate the member with an active company branch and position.
        - Record the member creation through the centralized auditing subsystem.

        Notes:
        - Branch and position tenant validation is performed by the serializer before this operation.
        - Company ownership is controlled exclusively by the backend.
        - The operation does not create an authentication user.
        - The audit event contains operational identity information only.
    """

    member = Member.objects.create(company=company, created_by=actor, updated_by=actor, **validated_data)

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.MEMBER,
        action=AUDIT_ACTION_REGISTRY.CREATE,
        description="Miembro creado en Dialoqo.",
        actor=actor,
        company=company,
        branch=member.branch,
        target=member,
        metadata={
            "member_id": member.id,
            "company_id": company.id,
            "branch_id": member.branch_id,
            "position_id": member.position_id,
            "member_code": member.member_code,
            "first_name": member.first_name,
            "last_name": member.last_name,
            "email": member.email,
            "is_active": member.is_active,
        },
    )

    return member


@transaction.atomic
def update_member(member, validated_data, actor):
    """
        DOCSTRING: Update Member

        Description:
        - Apply validated changes to an existing Dialoqo member.
        - Preserve the member inside the existing company tenant.
        - Record the operational change through the centralized auditing subsystem.

        Notes:
        - The company relationship cannot be changed through this operation.
        - Branch and position changes are allowed only after serializer tenant validation.
        - Previous and current values are preserved for traceability.
        - Model relationships are stored in audit metadata through their identifiers.
    """

    locked_member = Member.objects.select_for_update().select_related("company", "branch", "position").get(id=member.id)

    changed_fields = list(validated_data.keys())
    previous_values = {}

    for field in changed_fields:
        if field == "branch":
            previous_values["branch_id"] = locked_member.branch_id
        elif field == "position":
            previous_values["position_id"] = locked_member.position_id
        else:
            previous_values[field] = getattr(locked_member, field)

    for field, value in validated_data.items():
        setattr(locked_member, field, value)

    locked_member.updated_by = actor
    locked_member.save()

    current_values = {}

    for field in changed_fields:
        if field == "branch":
            current_values["branch_id"] = locked_member.branch_id
        elif field == "position":
            current_values["position_id"] = locked_member.position_id
        else:
            current_values[field] = getattr(locked_member, field)

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.MEMBER,
        action=AUDIT_ACTION_REGISTRY.UPDATE,
        description="Miembro actualizado en Dialoqo.",
        actor=actor,
        company=locked_member.company,
        branch=locked_member.branch,
        target=locked_member,
        metadata={
            "member_id": locked_member.id,
            "company_id": locked_member.company_id,
            "changed_fields": changed_fields,
            "previous_values": previous_values,
            "current_values": current_values,
        },
    )

    return locked_member


@transaction.atomic
def deactivate_member(member, actor):
    """
        DOCSTRING: Deactivate Member

        Description:
        - Deactivate a Dialoqo member without deleting historical operational information.
        - Record the member lifecycle change through the centralized auditing subsystem.

        Notes:
        - Historical number assignments remain preserved.
        - The operation is rejected when the member is already inactive.
        - Deactivation does not modify historical assignment records.
    """

    locked_member = Member.objects.select_for_update().select_related("company", "branch", "position").get(id=member.id)

    if not locked_member.is_active:
        raise ValidationError({"member": "Desactivación de miembro rechazada: el miembro ya se encuentra inactivo."})

    locked_member.is_active = False
    locked_member.updated_by = actor
    locked_member.save(update_fields=["is_active", "updated_by", "updated_at"])

    schedule_audit_event(
        category=AUDIT_CATEGORY_REGISTRY.MEMBER,
        action=AUDIT_ACTION_REGISTRY.DEACTIVATE,
        description="Miembro desactivado en Dialoqo.",
        actor=actor,
        company=locked_member.company,
        branch=locked_member.branch,
        target=locked_member,
        metadata={
            "member_id": locked_member.id,
            "company_id": locked_member.company_id,
            "branch_id": locked_member.branch_id,
            "position_id": locked_member.position_id,
            "member_code": locked_member.member_code,
            "first_name": locked_member.first_name,
            "last_name": locked_member.last_name,
            "email": locked_member.email,
            "is_active": locked_member.is_active,
        },
    )

    return locked_member