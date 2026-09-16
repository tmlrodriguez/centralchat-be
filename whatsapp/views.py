import hashlib
import hmac
import json
import secrets
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN
from rest_framework.views import APIView
from access.registry import ROLE_REGISTRY
from organizations.models import Branch, Company, UserCompanyAccess
from auditing.operations import schedule_audit_event
from auditing.registry import AUDIT_ACTION_REGISTRY, AUDIT_CATEGORY_REGISTRY
from organizations.permissions import IsOrganizationAdministrator
from .credentials import get_meta_credentials
from .meta import MetaWhatsAppAPIError
from .models import Conversation, ConversationReadState, MediaAttachment, Message, NumberAssignment, WhatsAppBusinessAccount, WhatsAppNumber
from .operations import activate_whatsapp_monitoring, assign_whatsapp_number, deactivate_whatsapp_monitoring, get_current_whatsapp_number_assignment, mark_conversation_as_read, send_outbound_whatsapp_text_message, unassign_whatsapp_number
from .pagination import ConversationPagination, MessagePagination
from .permissions import IsMember, IsMonitoringUser
from .resolvers import resolve_administrative_company, resolve_company_branch, resolve_company_whatsapp_business_account, resolve_company_whatsapp_number, resolve_conversation_message, resolve_message_media_attachment, resolve_monitoring_whatsapp_number, resolve_whatsapp_number_assignment, resolve_whatsapp_number_conversation
from .serializers.business import ConversationSerializer, MediaAttachmentSerializer, MessageSerializer, NumberAssignmentSerializer, OutboundTextMessageSerializer, WhatsAppBusinessAccountSerializer, WhatsAppNumberSerializer
from .serializers.snapshots import ConversationReadStateSnapshotSerializer, ConversationSnapshotSerializer, MediaAttachmentSnapshotSerializer, NumberAssignmentSnapshotSerializer, WhatsAppBusinessAccountSnapshotSerializer, WhatsAppNumberSnapshotSerializer
from .serializers.monitoring import MonitoringCompanySerializer
from .tasks import process_whatsapp_webhook_task

# Define your views here.

class WhatsAppBusinessAccountView(APIView):
    """
        DOCSTRING: WhatsApp Business Account View

        Description:
        - Return active WhatsApp Business Accounts belonging to a specific active company.
        - Create, partially update, and deactivate WhatsApp Business Account records.
        - Record administrative WABA mutations through the centralized audit subsystem.

        Notes:
        - The company identifier is required for every operation.
        - The company must belong to the authenticated administrative user.
        - The WABA is scoped directly to the same company.
        - Foreign WABA identifiers are treated as nonexistent.
        - Audit records are persisted only after successful database commit.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = WhatsAppBusinessAccountSerializer
    snapshot_serializer = WhatsAppBusinessAccountSnapshotSerializer

    def get(self, request, company_id, account_id=None):
        company = resolve_administrative_company(user=request.user, company_id=company_id)

        accounts = WhatsAppBusinessAccount.objects.select_related(
            "company",
        ).filter(
            company=company,
            is_active=True,
        )

        if account_id:
            account = resolve_company_whatsapp_business_account(company=company, account_id=account_id)

            response_payload = {
                "success_message": "Cuenta de WhatsApp Business extraída correctamente.",
                "data": self.business_serializer(account, context={"company": company}).data,
            }

            return Response(response_payload, status=HTTP_200_OK)

        response_payload = {
            "success_message": "Cuentas de WhatsApp Business extraídas correctamente.",
            "data": self.snapshot_serializer(accounts, many=True).data,
        }

        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request, company_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        serializer = self.business_serializer(data=request.data, context={"company": company})

        if not serializer.is_valid():
            response_payload = {
                "error_message": "Creación de cuenta de WhatsApp Business rechazada: los datos proporcionados no son válidos.",
                "data": serializer.errors,
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            account = serializer.save(company=company, created_by=request.user, updated_by=request.user)

            schedule_audit_event(
                category=AUDIT_CATEGORY_REGISTRY.WHATSAPP,
                action=AUDIT_ACTION_REGISTRY.CREATE,
                description="Cuenta de WhatsApp Business creada en Dialoqo.",
                actor=request.user,
                company=company,
                target=account,
                metadata={
                    "whatsapp_business_account_id": account.id,
                    "meta_waba_id": account.meta_waba_id,
                    "meta_business_id": account.meta_business_id,
                    "is_connected": account.is_connected,
                    "is_webhook_configured": account.is_webhook_configured,
                    "is_active": account.is_active,
                },
            )

        response_payload = {
            "success_message": "Cuenta de WhatsApp Business creada correctamente.",
            "data": self.business_serializer(account, context={"company": company}).data,
        }

        return Response(response_payload, status=HTTP_201_CREATED)

    def patch(self, request, company_id, account_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        account = resolve_company_whatsapp_business_account(company=company, account_id=account_id)
        serializer = self.business_serializer(account, data=request.data, partial=True, context={"company": company})

        if not serializer.is_valid():
            response_payload = {
                "error_message": "Actualización de cuenta de WhatsApp Business rechazada: los datos proporcionados no son válidos.",
                "data": serializer.errors,
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        changed_fields = list(serializer.validated_data.keys())

        with transaction.atomic():
            account = serializer.save(updated_by=request.user)

            schedule_audit_event(
                category=AUDIT_CATEGORY_REGISTRY.WHATSAPP,
                action=AUDIT_ACTION_REGISTRY.UPDATE,
                description="Cuenta de WhatsApp Business actualizada en Dialoqo.",
                actor=request.user,
                company=company,
                target=account,
                metadata={
                    "whatsapp_business_account_id": account.id,
                    "meta_waba_id": account.meta_waba_id,
                    "changed_fields": changed_fields,
                    "is_connected": account.is_connected,
                    "is_webhook_configured": account.is_webhook_configured,
                    "is_active": account.is_active,
                },
            )

        response_payload = {
            "success_message": "Cuenta de WhatsApp Business actualizada correctamente.",
            "data": self.business_serializer(account, context={"company": company}).data,
        }

        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id, account_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        account = resolve_company_whatsapp_business_account(company=company, account_id=account_id)

        if account.numbers.filter(company=company, is_active=True).exists():
            response_payload = {
                "error_message": "Desactivación de cuenta rechazada: existen números de WhatsApp activos asociados.",
                "data": {},
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            account.is_active = False
            account.updated_by = request.user
            account.save(update_fields=["is_active", "updated_by", "updated_at"])

            schedule_audit_event(
                category=AUDIT_CATEGORY_REGISTRY.WHATSAPP,
                action=AUDIT_ACTION_REGISTRY.DEACTIVATE,
                description="Cuenta de WhatsApp Business desactivada en Dialoqo.",
                actor=request.user,
                company=company,
                target=account,
                metadata={
                    "whatsapp_business_account_id": account.id,
                    "meta_waba_id": account.meta_waba_id,
                    "is_connected": account.is_connected,
                    "is_webhook_configured": account.is_webhook_configured,
                    "is_active": account.is_active,
                },
            )

        response_payload = {
            "success_message": "Cuenta de WhatsApp Business desactivada correctamente.",
            "data": self.business_serializer(account, context={"company": company}).data,
        }

        return Response(response_payload, status=HTTP_200_OK)


class WhatsAppNumberView(APIView):
    """
        DOCSTRING: WhatsApp Number View

        Description:
        - Return active WhatsApp numbers belonging to a specific company and branch.
        - Create, partially update, and deactivate corporate WhatsApp numbers.
        - Record administrative number mutations through the centralized audit subsystem.

        Notes:
        - Company and branch identifiers are tenant-scoped.
        - The associated WABA must remain inside the same company.
        - Foreign number identifiers are treated as nonexistent.
        - Audit metadata intentionally avoids unnecessary conversation content.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = WhatsAppNumberSerializer
    snapshot_serializer = WhatsAppNumberSnapshotSerializer

    def get(self, request, company_id, branch_id, number_id=None):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)

        numbers = WhatsAppNumber.objects.select_related(
            "company",
            "branch",
            "whatsapp_business_account",
            "whatsapp_business_account__company",
        ).filter(
            company=company,
            branch=branch,
            branch__company=company,
            whatsapp_business_account__company=company,
            is_active=True,
        )

        if number_id:
            whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)

            response_payload = {
                "success_message": "Número de WhatsApp extraído correctamente.",
                "data": self.business_serializer(whatsapp_number, context={"company": company}).data,
            }

            return Response(response_payload, status=HTTP_200_OK)

        response_payload = {
            "success_message": "Números de WhatsApp extraídos correctamente.",
            "data": self.snapshot_serializer(numbers, many=True).data,
        }

        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request, company_id, branch_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        serializer = self.business_serializer(data=request.data, context={"company": company})

        if not serializer.is_valid():
            response_payload = {
                "error_message": "Creación de número de WhatsApp rechazada: los datos proporcionados no son válidos.",
                "data": serializer.errors,
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            whatsapp_number = serializer.save(company=company, branch=branch, created_by=request.user, updated_by=request.user)

            schedule_audit_event(
                category=AUDIT_CATEGORY_REGISTRY.WHATSAPP,
                action=AUDIT_ACTION_REGISTRY.CREATE,
                description="Número de WhatsApp creado en Dialoqo.",
                actor=request.user,
                company=company,
                branch=branch,
                target=whatsapp_number,
                metadata={
                    "whatsapp_number_id": whatsapp_number.id,
                    "whatsapp_business_account_id": whatsapp_number.whatsapp_business_account_id,
                    "meta_phone_number_id": whatsapp_number.meta_phone_number_id,
                    "is_connected": whatsapp_number.is_connected,
                    "is_monitoring_enabled": whatsapp_number.is_monitoring_enabled,
                    "is_active": whatsapp_number.is_active,
                },
            )

        response_payload = {
            "success_message": "Número de WhatsApp creado correctamente.",
            "data": self.business_serializer(whatsapp_number, context={"company": company}).data,
        }

        return Response(response_payload, status=HTTP_201_CREATED)

    def patch(self, request, company_id, branch_id, number_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)
        serializer = self.business_serializer(whatsapp_number, data=request.data, partial=True, context={"company": company})

        if not serializer.is_valid():
            response_payload = {
                "error_message": "Actualización de número de WhatsApp rechazada: los datos proporcionados no son válidos.",
                "data": serializer.errors,
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        changed_fields = list(serializer.validated_data.keys())
        previous_waba_id = whatsapp_number.whatsapp_business_account_id

        with transaction.atomic():
            whatsapp_number = serializer.save(company=company, branch=branch, updated_by=request.user)

            schedule_audit_event(
                category=AUDIT_CATEGORY_REGISTRY.WHATSAPP,
                action=AUDIT_ACTION_REGISTRY.UPDATE,
                description="Número de WhatsApp actualizado en Dialoqo.",
                actor=request.user,
                company=company,
                branch=branch,
                target=whatsapp_number,
                metadata={
                    "whatsapp_number_id": whatsapp_number.id,
                    "previous_whatsapp_business_account_id": previous_waba_id,
                    "current_whatsapp_business_account_id": whatsapp_number.whatsapp_business_account_id,
                    "meta_phone_number_id": whatsapp_number.meta_phone_number_id,
                    "changed_fields": changed_fields,
                    "is_connected": whatsapp_number.is_connected,
                    "is_monitoring_enabled": whatsapp_number.is_monitoring_enabled,
                    "is_active": whatsapp_number.is_active,
                },
            )

        response_payload = {
            "success_message": "Número de WhatsApp actualizado correctamente.",
            "data": self.business_serializer(whatsapp_number, context={"company": company}).data,
        }

        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id, branch_id, number_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)

        if whatsapp_number.is_monitoring_enabled:
            response_payload = {
                "error_message": "Desactivación de número rechazada: el monitoreo se encuentra activo.",
                "data": {},
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            whatsapp_number.is_active = False
            whatsapp_number.updated_by = request.user
            whatsapp_number.save(update_fields=["is_active", "updated_by", "updated_at"])

            schedule_audit_event(
                category=AUDIT_CATEGORY_REGISTRY.WHATSAPP,
                action=AUDIT_ACTION_REGISTRY.DEACTIVATE,
                description="Número de WhatsApp desactivado en Dialoqo.",
                actor=request.user,
                company=company,
                branch=branch,
                target=whatsapp_number,
                metadata={
                    "whatsapp_number_id": whatsapp_number.id,
                    "whatsapp_business_account_id": whatsapp_number.whatsapp_business_account_id,
                    "meta_phone_number_id": whatsapp_number.meta_phone_number_id,
                    "is_connected": whatsapp_number.is_connected,
                    "is_monitoring_enabled": whatsapp_number.is_monitoring_enabled,
                    "is_active": whatsapp_number.is_active,
                },
            )

        response_payload = {
            "success_message": "Número de WhatsApp desactivado correctamente.",
            "data": self.business_serializer(whatsapp_number, context={"company": company}).data,
        }

        return Response(response_payload, status=HTTP_200_OK)


class WhatsAppMonitoringView(APIView):
    """
        DOCSTRING: WhatsApp Monitoring View

        Description:
        - Activate and deactivate monitored message capture for a corporate WhatsApp number.

        Notes:
        - The number is resolved through the full administrative company and branch tenant hierarchy.
        - Foreign number identifiers return not found.
        - Monitoring lifecycle auditing is implemented inside the operation layer.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    snapshot_serializer = WhatsAppNumberSnapshotSerializer

    def post(self, request, company_id, branch_id, number_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)

        try:
            whatsapp_number = activate_whatsapp_monitoring(whatsapp_number=whatsapp_number, actor=request.user)

        except ValidationError as error:
            response_payload = {
                "error_message": "Activación de monitoreo rechazada: no fue posible completar la operación.",
                "data": error.message_dict,
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        response_payload = {
            "success_message": "Monitoreo de WhatsApp activado correctamente.",
            "data": self.snapshot_serializer(whatsapp_number).data,
        }

        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id, branch_id, number_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)

        try:
            whatsapp_number = deactivate_whatsapp_monitoring(whatsapp_number=whatsapp_number, actor=request.user)

        except ValidationError as error:
            response_payload = {
                "error_message": "Desactivación de monitoreo rechazada: no fue posible completar la operación.",
                "data": error.message_dict,
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        response_payload = {
            "success_message": "Monitoreo de WhatsApp desactivado correctamente.",
            "data": self.snapshot_serializer(whatsapp_number).data,
        }

        return Response(response_payload, status=HTTP_200_OK)


class MonitoringContextView(APIView):
    """
        DOCSTRING: Monitoring Context View

        Description:
        - Return the complete monitoring context available to the authenticated MONITOR or MEMBER user.
        - Provide authorized companies, active branches, and operational WhatsApp numbers.
        - Supply the hierarchical context required by the Dialoqo monitoring frontend.

        Notes:
        - MONITOR users receive operational numbers through active company-access assignments.
        - MEMBER users receive only operational numbers currently assigned to them.
        - Only active companies, branches, WABA accounts, connected numbers, and monitoring-enabled numbers are returned.
        - This operation is read-only and does not generate audit events.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitoringUser]
    serializer_class = MonitoringCompanySerializer

    def get(self, request):
        if request.user.role == ROLE_REGISTRY.MONITOR:
            authorized_company_ids = UserCompanyAccess.objects.filter(
                user=request.user,
                is_active=True,
                company__is_active=True,
            ).values_list("company_id", flat=True)

            monitoring_numbers = WhatsAppNumber.objects.select_related(
                "company",
                "branch",
                "whatsapp_business_account",
            ).filter(
                company_id__in=authorized_company_ids,
                company__is_active=True,
                branch__is_active=True,
                whatsapp_business_account__is_active=True,
                is_active=True,
                is_connected=True,
                is_monitoring_enabled=True,
            ).order_by("display_name", "id")

        else:
            assigned_number_ids = NumberAssignment.objects.filter(
                member=request.user,
                member__is_active=True,
                is_active=True,
                unassigned_at__isnull=True,
                whatsapp_number__company__is_active=True,
                whatsapp_number__branch__is_active=True,
                whatsapp_number__whatsapp_business_account__is_active=True,
                whatsapp_number__is_active=True,
                whatsapp_number__is_connected=True,
                whatsapp_number__is_monitoring_enabled=True,
            ).values_list("whatsapp_number_id", flat=True)

            monitoring_numbers = WhatsAppNumber.objects.select_related(
                "company",
                "branch",
                "whatsapp_business_account",
            ).filter(
                id__in=assigned_number_ids,
                company__is_active=True,
                branch__is_active=True,
                whatsapp_business_account__is_active=True,
                is_active=True,
                is_connected=True,
                is_monitoring_enabled=True,
            ).order_by("display_name", "id")

            authorized_company_ids = monitoring_numbers.values_list("company_id", flat=True)

        monitoring_branches = Branch.objects.filter(
            company_id__in=authorized_company_ids,
            company__is_active=True,
            is_active=True,
            whatsapp_numbers__in=monitoring_numbers,
        ).distinct().order_by("name", "id").prefetch_related(
            Prefetch("whatsapp_numbers", queryset=monitoring_numbers, to_attr="monitoring_numbers")
        )

        companies = Company.objects.filter(
            id__in=authorized_company_ids,
            is_active=True,
            branches__in=monitoring_branches,
        ).distinct().order_by("name", "id").prefetch_related(
            Prefetch("branches", queryset=monitoring_branches, to_attr="monitoring_branches")
        )

        response_payload = {
            "success_message": "Contexto de monitoreo extraído correctamente.",
            "data": self.serializer_class(companies, many=True).data,
        }

        return Response(response_payload, status=HTTP_200_OK)


class NumberAssignmentView(APIView):
    """
        DOCSTRING: Number Assignment View

        Description:
        - Return current and historical assignments associated with a corporate WhatsApp number.
        - Assign or reassign the number to an eligible Dialoqo MEMBER user.
        - End the currently active assignment.

        Notes:
        - Company, branch, and WhatsApp number relationships remain tenant-scoped.
        - Eligible members are AccessUser records with role MEMBER owned by the same administrator.
        - Historical assignments remain preserved.
        - Assignment lifecycle auditing is implemented inside the operation layer.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = NumberAssignmentSerializer
    snapshot_serializer = NumberAssignmentSnapshotSerializer

    def get(self, request, company_id, branch_id, number_id, assignment_id=None):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)

        assignments = NumberAssignment.objects.select_related("member").filter(
            whatsapp_number=whatsapp_number,
            member__created_by=request.user,
        ).order_by("-assigned_at", "-id")

        if assignment_id:
            assignment = resolve_whatsapp_number_assignment(whatsapp_number=whatsapp_number, assignment_id=assignment_id)

            response_payload = {
                "success_message": "Asignación de número extraída correctamente.",
                "data": self.snapshot_serializer(assignment).data,
            }

            return Response(response_payload, status=HTTP_200_OK)

        current_assignment = get_current_whatsapp_number_assignment(whatsapp_number=whatsapp_number)

        response_payload = {
            "success_message": "Historial de asignaciones extraído correctamente.",
            "data": {
                "current_assignment": self.snapshot_serializer(current_assignment).data if current_assignment else None,
                "history": self.snapshot_serializer(assignments, many=True).data,
            },
        }

        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request, company_id, branch_id, number_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)
        serializer = self.business_serializer(data=request.data, context={"whatsapp_number": whatsapp_number})

        if not serializer.is_valid():
            response_payload = {
                "error_message": "Asignación de número rechazada: los datos proporcionados no son válidos.",
                "data": serializer.errors,
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        try:
            assignment = assign_whatsapp_number(
                whatsapp_number=whatsapp_number,
                member=serializer.validated_data["member"],
                actor=request.user,
            )

        except ValidationError as error:
            response_payload = {
                "error_message": "Asignación de número rechazada: no fue posible completar la operación.",
                "data": error.message_dict,
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        response_payload = {
            "success_message": "Número de WhatsApp asignado correctamente.",
            "data": self.snapshot_serializer(assignment).data,
        }

        return Response(response_payload, status=HTTP_201_CREATED)

    def delete(self, request, company_id, branch_id, number_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)

        try:
            assignment = unassign_whatsapp_number(whatsapp_number=whatsapp_number, actor=request.user)

        except ValidationError as error:
            response_payload = {
                "error_message": "Desasignación de número rechazada: no fue posible completar la operación.",
                "data": error.message_dict,
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        response_payload = {
            "success_message": "Número de WhatsApp desasignado correctamente.",
            "data": self.snapshot_serializer(assignment).data,
        }

        return Response(response_payload, status=HTTP_200_OK)


class ConversationView(APIView):
    """
        DOCSTRING: Conversation View

        Description:
        - Return paginated monitored conversations belonging to a corporate WhatsApp number.
        - Return detailed information for a specific monitored conversation.
        - Support search, unread filtering, current-member assignment filtering, and explicit ordering.

        Notes:
        - MONITOR and MEMBER users may access conversation content according to their role-specific authorization.
        - MONITOR users are authorized through company access.
        - MEMBER users are authorized through the active assignment of the requested WhatsApp number.
        - Conversations are resolved inside that number and company.
        - Foreign conversation identifiers therefore behave as nonexistent.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitoringUser]
    business_serializer = ConversationSerializer
    snapshot_serializer = ConversationSnapshotSerializer
    pagination_class = ConversationPagination

    def get(self, request, company_id, branch_id, number_id, conversation_id=None):
        whatsapp_number = resolve_monitoring_whatsapp_number(user=request.user, company_id=company_id, branch_id=branch_id, number_id=number_id)
        current_assignment = get_current_whatsapp_number_assignment(whatsapp_number=whatsapp_number)

        if conversation_id:
            conversation = resolve_whatsapp_number_conversation(whatsapp_number=whatsapp_number, conversation_id=conversation_id)

            response_payload = {
                "success_message": "Conversación extraída correctamente.",
                "data": self.business_serializer(
                    conversation,
                    context={
                        "request": request,
                        "current_assignment": current_assignment,
                    },
                ).data,
            }

            return Response(response_payload, status=HTTP_200_OK)

        conversations = Conversation.objects.select_related(
            "customer",
            "last_message",
            "last_message__context_message",
        ).prefetch_related(
            "last_message__media_attachments",
            Prefetch(
                "read_states",
                queryset=ConversationReadState.objects.filter(user=request.user),
                to_attr="current_user_read_states",
            ),
        ).filter(
            whatsapp_number=whatsapp_number,
            whatsapp_number__company=whatsapp_number.company,
            customer__company=whatsapp_number.company,
            is_active=True,
        )

        search = request.query_params.get("search", "").strip()
        unread = request.query_params.get("unread")
        member_id = request.query_params.get("member_id")
        ordering = request.query_params.get("ordering", "-last_message_at")

        if search:
            conversations = conversations.filter(
                Q(customer__phone_number__icontains=search)
                | Q(customer__display_name__icontains=search)
                | Q(customer__profile_name__icontains=search)
            )

        if unread is not None:
            normalized_unread = unread.strip().lower()

            if normalized_unread in ["true", "1", "yes"]:
                conversations = conversations.filter(
                    read_states__user=request.user,
                    read_states__is_read=False,
                    read_states__unread_count__gt=0,
                )

            elif normalized_unread in ["false", "0", "no"]:
                conversations = conversations.filter(
                    Q(read_states__user=request.user, read_states__is_read=True)
                    | Q(read_states__user=request.user, read_states__unread_count=0)
                    | ~Q(read_states__user=request.user)
                )

            else:
                response_payload = {
                    "error_message": "Filtro de conversaciones rechazado: unread contiene un valor inválido.",
                    "data": {
                        "unread": "Valores permitidos: true, false, 1, 0, yes, no.",
                    },
                }

                return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        if member_id is not None:
            try:
                member_id = int(member_id)

            except (TypeError, ValueError):
                response_payload = {
                    "error_message": "Filtro de conversaciones rechazado: member_id no contiene un identificador válido.",
                    "data": {
                        "member_id": "Debe proporcionar un identificador numérico válido.",
                    },
                }

                return Response(response_payload, status=HTTP_400_BAD_REQUEST)

            if current_assignment is None or current_assignment.member_id != member_id:
                conversations = conversations.none()

        allowed_ordering = ["last_message_at", "-last_message_at", "created_at", "-created_at"]

        if ordering not in allowed_ordering:
            response_payload = {
                "error_message": "Ordenamiento de conversaciones rechazado: el criterio proporcionado no es válido.",
                "data": {
                    "ordering": f"Valores permitidos: {', '.join(allowed_ordering)}.",
                },
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        conversations = conversations.order_by(ordering, "-id").distinct()
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(conversations, request, view=self)

        for conversation in page:
            conversation.current_user_read_state = conversation.current_user_read_states[0] if conversation.current_user_read_states else None

        response_data = self.snapshot_serializer(
            page,
            many=True,
            context={
                "request": request,
                "current_assignment": current_assignment,
            },
        ).data

        return paginator.get_paginated_response(response_data)


class ConversationReadView(APIView):
    """
        DOCSTRING: Conversation Read View

        Description:
        - Mark a monitored conversation as read for the authenticated monitoring user.

        Notes:
        - Company, number, and conversation resolution remain tenant-scoped.
        - A conversation belonging to another company or number cannot be marked as read.
        - Read acknowledgement auditing is implemented inside the operation layer.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitoringUser]
    snapshot_serializer = ConversationReadStateSnapshotSerializer

    def post(self, request, company_id, branch_id, number_id, conversation_id):
        whatsapp_number = resolve_monitoring_whatsapp_number(user=request.user, company_id=company_id, branch_id=branch_id, number_id=number_id)
        conversation = resolve_whatsapp_number_conversation(whatsapp_number=whatsapp_number, conversation_id=conversation_id)
        read_state = mark_conversation_as_read(conversation=conversation, user=request.user)

        response_payload = {
            "success_message": "Conversación marcada como leída correctamente.",
            "data": self.snapshot_serializer(read_state).data,
        }

        return Response(response_payload, status=HTTP_200_OK)


class MessageView(APIView):
    """
        DOCSTRING: Message View

        Description:
        - Return paginated persisted monitored messages belonging to a specific conversation.
        - Return detailed information for a specific monitored message.

        Notes:
        - Company, number, conversation, and message are resolved hierarchically.
        - Foreign message identifiers return not found.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitoringUser]
    business_serializer = MessageSerializer
    pagination_class = MessagePagination

    def get(self, request, company_id, branch_id, number_id, conversation_id, message_id=None):
        whatsapp_number = resolve_monitoring_whatsapp_number(user=request.user, company_id=company_id, branch_id=branch_id, number_id=number_id)
        conversation = resolve_whatsapp_number_conversation(whatsapp_number=whatsapp_number, conversation_id=conversation_id)

        messages = Message.objects.select_related(
            "context_message",
            "conversation",
        ).prefetch_related(
            "media_attachments",
        ).filter(
            conversation=conversation,
            conversation__whatsapp_number=whatsapp_number,
            conversation__customer__company=whatsapp_number.company,
            is_active=True,
        )

        if message_id:
            message = resolve_conversation_message(conversation=conversation, message_id=message_id)

            response_payload = {
                "success_message": "Mensaje extraído correctamente.",
                "data": self.business_serializer(message).data,
            }

            return Response(response_payload, status=HTTP_200_OK)

        ordering = request.query_params.get("ordering", "message_timestamp")
        allowed_ordering = ["message_timestamp", "-message_timestamp"]

        if ordering not in allowed_ordering:
            response_payload = {
                "error_message": "Ordenamiento de mensajes rechazado: el criterio proporcionado no es válido.",
                "data": {
                    "ordering": f"Valores permitidos: {', '.join(allowed_ordering)}.",
                },
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        messages = messages.order_by(
            ordering,
            "id" if ordering == "message_timestamp" else "-id",
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(messages, request, view=self)
        response_data = self.business_serializer(page, many=True).data

        return paginator.get_paginated_response(response_data)


class MediaAttachmentView(APIView):
    """
        DOCSTRING: Media Attachment View

        Description:
        - Return media attachment metadata belonging to a monitored WhatsApp message.

        Notes:
        - Every parent resource is resolved before the attachment.
        - Foreign attachment identifiers return not found.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitoringUser]
    business_serializer = MediaAttachmentSerializer
    snapshot_serializer = MediaAttachmentSnapshotSerializer

    def get(self, request, company_id, branch_id, number_id, conversation_id, message_id, attachment_id=None):
        whatsapp_number = resolve_monitoring_whatsapp_number(user=request.user, company_id=company_id, branch_id=branch_id, number_id=number_id)
        conversation = resolve_whatsapp_number_conversation(whatsapp_number=whatsapp_number, conversation_id=conversation_id)
        message = resolve_conversation_message(conversation=conversation, message_id=message_id)

        attachments = MediaAttachment.objects.filter(
            message=message,
            message__conversation=conversation,
            is_active=True,
        )

        if attachment_id:
            attachment = resolve_message_media_attachment(message=message, attachment_id=attachment_id)

            response_payload = {
                "success_message": "Adjunto multimedia extraído correctamente.",
                "data": self.business_serializer(attachment).data,
            }

            return Response(response_payload, status=HTTP_200_OK)

        response_payload = {
            "success_message": "Adjuntos multimedia extraídos correctamente.",
            "data": self.snapshot_serializer(attachments, many=True).data,
        }

        return Response(response_payload, status=HTTP_200_OK)


class MetaWebhookView(APIView):
    """
        DOCSTRING: Meta Webhook View

        Description:
        - Provide the single public webhook endpoint used by the Dialoqo Meta application.
        - Authenticate Meta requests synchronously using global platform credentials.
        - Queue validated webhook payloads for asynchronous tenant resolution and persistence.

        Notes:
        - This endpoint does not require Dialoqo authentication.
        - All customer WABAs connected to the Dialoqo Meta application deliver events to this endpoint.
        - GET verification remains synchronous because Meta requires the challenge response.
        - POST signature validation remains synchronous because untrusted payloads must never enter the task broker.
        - Company ownership is resolved later from the globally unique Meta Phone Number ID in the payload.
        - Sensitive Meta credentials are never passed to Celery.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        mode = request.query_params.get("hub.mode")
        supplied_verify_token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if not mode or not supplied_verify_token or challenge is None:
            response_payload = {
                "error_message": "Verificación de webhook rechazada: los parámetros requeridos no fueron proporcionados.",
                "data": {},
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        try:
            credentials = get_meta_credentials()
        except ImproperlyConfigured:
            response_payload = {
                "error_message": "Verificación de webhook rechazada: la configuración global de Meta no se encuentra disponible.",
                "data": {},
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        if mode != "subscribe":
            response_payload = {
                "error_message": "Verificación de webhook rechazada: el modo de verificación no es válido.",
                "data": {},
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        if not secrets.compare_digest(supplied_verify_token, credentials["verify_token"]):
            response_payload = {
                "error_message": "Verificación de webhook rechazada: el token de verificación no es válido.",
                "data": {},
            }

            return Response(response_payload, status=HTTP_403_FORBIDDEN)

        return HttpResponse(challenge, status=HTTP_200_OK, content_type="text/plain")

    def post(self, request):
        try:
            credentials = get_meta_credentials()
        except ImproperlyConfigured:
            response_payload = {
                "error_message": "Recepción de webhook rechazada: la configuración global de Meta no se encuentra disponible.",
                "data": {},
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        signature_header = request.headers.get("X-Hub-Signature-256")

        if not signature_header:
            response_payload = {
                "error_message": "Recepción de webhook rechazada: la firma de Meta no fue proporcionada.",
                "data": {},
            }

            return Response(response_payload, status=HTTP_403_FORBIDDEN)

        expected_signature = "sha256=" + hmac.new(
            credentials["app_secret"].encode("utf-8"),
            request.body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature_header, expected_signature):
            response_payload = {
                "error_message": "Recepción de webhook rechazada: la firma de Meta no es válida.",
                "data": {},
            }

            return Response(response_payload, status=HTTP_403_FORBIDDEN)

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            response_payload = {
                "error_message": "Recepción de webhook rechazada: el contenido recibido no contiene JSON válido.",
                "data": {},
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        try:
            task = process_whatsapp_webhook_task.delay(payload)
        except Exception:
            response_payload = {
                "error_message": "Recepción de webhook rechazada: no fue posible colocar el evento en procesamiento.",
                "data": {},
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        response_payload = {
            "success_message": "Webhook de Meta recibido correctamente.",
            "data": {
                "accepted": True,
                "task_id": task.id,
            },
        }

        return Response(response_payload, status=HTTP_200_OK)


class OutboundMessageView(APIView):
    """
        DOCSTRING: Outbound Message View

        Description:
        - Send a plain-text WhatsApp message from a monitored Dialoqo conversation.

        Notes:
        - The authenticated user must have active access to the requested company.
        - Number and conversation are resolved inside that company tenant.
        - Destination and source phone numbers are never accepted from request data.
        - A foreign conversation identifier cannot be used to send through another tenant.
        - Successful message-send auditing is implemented inside the operation layer.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMember]
    input_serializer = OutboundTextMessageSerializer
    output_serializer = MessageSerializer

    def post(self, request, company_id, branch_id, number_id, conversation_id):
        whatsapp_number = resolve_monitoring_whatsapp_number(user=request.user, company_id=company_id, branch_id=branch_id, number_id=number_id)
        conversation = resolve_whatsapp_number_conversation(whatsapp_number=whatsapp_number, conversation_id=conversation_id)
        serializer = self.input_serializer(data=request.data)

        if not serializer.is_valid():
            response_payload = {
                "error_message": "Envío de mensaje rechazado: los datos proporcionados no son válidos.",
                "data": serializer.errors,
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        try:
            result = send_outbound_whatsapp_text_message(
                conversation=conversation,
                text_body=serializer.validated_data["text_body"],
                actor=request.user,
            )

        except ValidationError as error:
            response_payload = {
                "error_message": "Envío de mensaje rechazado: no fue posible completar la operación.",
                "data": error.message_dict,
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        except MetaWhatsAppAPIError as error:
            response_payload = {
                "error_message": "Envío de mensaje rechazado: Meta no aceptó el mensaje.",
                "data": {
                    "meta": {
                        "http_status": error.http_status,
                        "error_code": error.meta_error_code,
                        "error_subcode": error.meta_error_subcode,
                        "message": error.error_message,
                    },
                },
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        message = result["message"]

        response_payload = {
            "success_message": "Mensaje enviado a Meta correctamente.",
            "data": self.output_serializer(message).data,
        }

        return Response(response_payload, status=HTTP_201_CREATED)