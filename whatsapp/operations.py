from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import NumberAssignment, WhatsAppNumber, Conversation, ConversationReadState


# Define your operations here.

@transaction.atomic
def assign_whatsapp_number(whatsapp_number, member, actor):
    """
        DOCSTRING: Assign WhatsApp Number

        Description:
        - Assign a member to a WhatsApp number.
        - End any existing active assignment before creating the new assignment.

        Notes:
        - Assignment history must always be preserved.
        - The operation executes atomically.
        - The WhatsApp number is locked to prevent concurrent active assignments.
        - Reassigning the number to the currently assigned member is rejected.
        - Only one active assignment may remain after the transaction completes.
    """
    locked_number = WhatsAppNumber.objects.select_for_update().get(id=whatsapp_number.id)
    current_assignment = NumberAssignment.objects.select_for_update().filter(whatsapp_number=locked_number, is_active=True).first()
    if current_assignment and current_assignment.member_id == member.id:
        raise ValidationError({"member": "Asignación de número rechazada: el miembro ya se encuentra asignado a este número."})
    if current_assignment:
        current_assignment.is_active = False
        current_assignment.unassigned_at = timezone.now()
        current_assignment.updated_by = actor
        current_assignment.save(update_fields=["is_active", "unassigned_at", "updated_by", "updated_at"])
    assignment = NumberAssignment.objects.create(whatsapp_number=locked_number, member=member, created_by=actor, updated_by=actor)
    return assignment


@transaction.atomic
def unassign_whatsapp_number(whatsapp_number, actor):
    """
        DOCSTRING: Unassign WhatsApp Number

        Description:
        - End the current active member assignment for a WhatsApp number.

        Notes:
        - The assignment record must remain preserved.
        - The operation executes atomically.
        - The WhatsApp number is locked while the assignment is closed.
        - An explicit validation error is returned when no active assignment exists.
    """
    locked_number = WhatsAppNumber.objects.select_for_update().get(id=whatsapp_number.id)
    assignment = NumberAssignment.objects.select_for_update().filter(whatsapp_number=locked_number, is_active=True).first()
    if assignment is None:
        raise ValidationError({"assignment": "Desasignación rechazada: el número no tiene una asignación activa."})
    assignment.is_active = False
    assignment.unassigned_at = timezone.now()
    assignment.updated_by = actor
    assignment.save(update_fields=["is_active", "unassigned_at", "updated_by", "updated_at"])
    return assignment


@transaction.atomic
def activate_whatsapp_monitoring(whatsapp_number, actor):
    """
        DOCSTRING: Activate WhatsApp Monitoring

        Description:
        - Activate monitored message capture for a configured WhatsApp number.
        - Establish the timestamp from which new monitored messages become eligible for persistence.

        Notes:
        - The WhatsApp number is locked while the monitoring lifecycle is changed.
        - The number, company, branch, and WhatsApp Business Account must remain active.
        - The number and WhatsApp Business Account must be connected.
        - The WhatsApp Business Account webhook must be configured.
        - Monitoring activation must not import historical messages.
        - monitoring_started_at defines the inclusive beginning of the current monitoring period.
    """
    locked_number = WhatsAppNumber.objects.select_for_update().select_related("company", "branch", "whatsapp_business_account").get(id=whatsapp_number.id)

    if not locked_number.is_active:
        raise ValidationError({"whatsapp_number": "Activación de monitoreo rechazada: el número de WhatsApp se encuentra inactivo."})
    if not locked_number.company.is_active:
        raise ValidationError({"company": "Activación de monitoreo rechazada: la empresa se encuentra inactiva."})
    if not locked_number.branch.is_active:
        raise ValidationError({"branch": "Activación de monitoreo rechazada: la sucursal se encuentra inactiva."})
    if not locked_number.whatsapp_business_account.is_active:
        raise ValidationError({"whatsapp_business_account": "Activación de monitoreo rechazada: la cuenta de WhatsApp Business se encuentra inactiva."})
    if not locked_number.whatsapp_business_account.is_connected:
        raise ValidationError({"whatsapp_business_account": "Activación de monitoreo rechazada: la cuenta de WhatsApp Business no se encuentra conectada."})
    if not locked_number.whatsapp_business_account.is_webhook_configured:
        raise ValidationError({"whatsapp_business_account": "Activación de monitoreo rechazada: el webhook de la cuenta de WhatsApp Business no se encuentra configurado."})
    if not locked_number.is_connected:
        raise ValidationError({"whatsapp_number": "Activación de monitoreo rechazada: el número de WhatsApp no se encuentra conectado."})
    if locked_number.is_monitoring_enabled:
        raise ValidationError({"whatsapp_number": "Activación de monitoreo rechazada: el monitoreo ya se encuentra activo."})

    locked_number.is_monitoring_enabled = True
    locked_number.monitoring_started_at = timezone.now()
    locked_number.monitoring_stopped_at = None
    locked_number.updated_by = actor
    locked_number.save(update_fields=["is_monitoring_enabled", "monitoring_started_at", "monitoring_stopped_at", "updated_by", "updated_at"])
    return locked_number


@transaction.atomic
def deactivate_whatsapp_monitoring(whatsapp_number, actor):
    """
        DOCSTRING: Deactivate WhatsApp Monitoring

        Description:
        - Stop monitored message capture for an active WhatsApp monitoring configuration.

        Notes:
        - The WhatsApp number is locked while the monitoring lifecycle is changed.
        - Previously captured messages remain preserved.
        - Messages received after monitoring_stopped_at must not become monitored history.
        - Deactivation does not disconnect the WhatsApp number from Meta.
    """
    locked_number = WhatsAppNumber.objects.select_for_update().get(id=whatsapp_number.id)
    if not locked_number.is_monitoring_enabled:
        raise ValidationError({"whatsapp_number": "Desactivación de monitoreo rechazada: el monitoreo no se encuentra activo."})
    locked_number.is_monitoring_enabled = False
    locked_number.monitoring_stopped_at = timezone.now()
    locked_number.updated_by = actor
    locked_number.save(update_fields=["is_monitoring_enabled", "monitoring_stopped_at", "updated_by", "updated_at"])
    return locked_number


@transaction.atomic
def mark_conversation_as_read(conversation, user):
    """
        DOCSTRING: Mark Conversation As Read

        Description:
        - Mark a monitored conversation as read for a specific monitoring user.
        - Reset the user's unread message counter for the conversation.
        - Record the most recent message acknowledged by the user.

        Notes:
        - Read state is maintained independently for every monitoring user.
        - Opening a conversation must not modify another monitoring user's read state.
        - The operation locks the conversation and read-state record to prevent concurrent state inconsistencies.
    """
    locked_conversation = Conversation.objects.select_for_update().select_related("last_message").get(id=conversation.id)

    read_state, created = ConversationReadState.objects.select_for_update().get_or_create(
        conversation=locked_conversation,
        user=user,
        defaults={
            "is_read": True,
            "unread_count": 0,
            "last_read_message": locked_conversation.last_message,
            "last_opened_at": timezone.now(),
        },
    )

    if not created:
        read_state.is_read = True
        read_state.unread_count = 0
        read_state.last_read_message = locked_conversation.last_message
        read_state.last_opened_at = timezone.now()
        read_state.save(update_fields=["is_read", "unread_count", "last_read_message", "last_opened_at", "updated_at"])
    return read_state


