import hashlib
import hmac
import json
import secrets
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN
from rest_framework.views import APIView
from access.permissions import IsMonitor
from organizations.permissions import IsOrganizationAdministrator
from .credentials import get_meta_credentials
from .meta import MetaWhatsAppAPIError
from .models import Conversation, ConversationReadState, MediaAttachment, Message, MetaIntegration, NumberAssignment, WhatsAppBusinessAccount, WhatsAppNumber
from .operations import activate_whatsapp_monitoring, assign_whatsapp_number, deactivate_whatsapp_monitoring, get_current_whatsapp_number_assignment, mark_conversation_as_read, send_outbound_whatsapp_text_message, unassign_whatsapp_number
from .pagination import ConversationPagination, MessagePagination
from .resolvers import resolve_administrative_company, resolve_company_branch, resolve_company_meta_integration, resolve_company_whatsapp_business_account, resolve_company_whatsapp_number, resolve_conversation_message, resolve_message_media_attachment, resolve_user_company_access, resolve_whatsapp_number_assignment, resolve_whatsapp_number_conversation
from .serializers.business import ConversationSerializer, MediaAttachmentSerializer, MessageSerializer, MetaIntegrationSerializer, NumberAssignmentSerializer, OutboundTextMessageSerializer, WhatsAppBusinessAccountSerializer, WhatsAppNumberSerializer
from .serializers.snapshots import ConversationReadStateSnapshotSerializer, ConversationSnapshotSerializer, MediaAttachmentSnapshotSerializer, MetaIntegrationSnapshotSerializer, NumberAssignmentSnapshotSerializer, WhatsAppBusinessAccountSnapshotSerializer, WhatsAppNumberSnapshotSerializer
from .tasks import process_whatsapp_webhook_task

# Define your views here.

class MetaIntegrationView(APIView):
    """
        DOCSTRING: Meta Integration View

        Description:
        - Return active Meta integrations configured for a specific company.
        - Create, partially update, and deactivate company-specific Meta integration records.

        Notes:
        - The company must belong to the authenticated administrative user.
        - Sensitive Meta credentials are maintained externally through credential_reference.
        - webhook_key is generated exclusively by the backend.
        - Integration records are deactivated instead of destructively deleted.
        - All integration resolution remains scoped to the administrative company tenant.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = MetaIntegrationSerializer
    snapshot_serializer = MetaIntegrationSnapshotSerializer

    def get(self, request, company_id, integration_id=None):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        integrations = MetaIntegration.objects.filter(company=company, company__is_active=True, is_active=True)

        if integration_id:
            integration = resolve_company_meta_integration(company=company, integration_id=integration_id)
            response_payload = {"success_message": "Integración de Meta extraída correctamente.", "data": self.business_serializer(integration).data}
            return Response(response_payload, status=HTTP_200_OK)

        response_payload = {"success_message": "Integraciones de Meta extraídas correctamente.", "data": self.snapshot_serializer(integrations, many=True).data}
        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request, company_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        serializer = self.business_serializer(data=request.data)

        if not serializer.is_valid():
            response_payload = {"error_message": "Creación de integración de Meta rechazada: los datos proporcionados no son válidos.", "data": serializer.errors}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        integration = serializer.save(company=company, created_by=request.user, updated_by=request.user)
        response_payload = {"success_message": "Integración de Meta creada correctamente.", "data": self.business_serializer(integration).data}
        return Response(response_payload, status=HTTP_201_CREATED)

    def patch(self, request, company_id, integration_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        integration = resolve_company_meta_integration(company=company, integration_id=integration_id)
        serializer = self.business_serializer(integration, data=request.data, partial=True)

        if not serializer.is_valid():
            response_payload = {"error_message": "Actualización de integración de Meta rechazada: los datos proporcionados no son válidos.", "data": serializer.errors}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        integration = serializer.save(updated_by=request.user)
        response_payload = {"success_message": "Integración de Meta actualizada correctamente.", "data": self.business_serializer(integration).data}
        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id, integration_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        integration = resolve_company_meta_integration(company=company, integration_id=integration_id)

        if integration.whatsapp_business_accounts.filter(company=company, is_active=True).exists():
            response_payload = {"error_message": "Desactivación de integración rechazada: existen cuentas de WhatsApp Business activas asociadas.", "data": {}}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        integration.is_active = False
        integration.updated_by = request.user
        integration.save(update_fields=["is_active", "updated_by", "updated_at"])

        response_payload = {"success_message": "Integración de Meta desactivada correctamente.", "data": self.business_serializer(integration).data}
        return Response(response_payload, status=HTTP_200_OK)


class WhatsAppBusinessAccountView(APIView):
    """
        DOCSTRING: WhatsApp Business Account View

        Description:
        - Return active WhatsApp Business Accounts belonging to a specific active company.
        - Create, partially update, and deactivate WhatsApp Business Account records.

        Notes:
        - The company identifier is required for every operation.
        - The company must belong to the authenticated administrative user.
        - The associated Meta integration must belong to exactly the same company.
        - Foreign WABA identifiers are treated as nonexistent.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = WhatsAppBusinessAccountSerializer
    snapshot_serializer = WhatsAppBusinessAccountSnapshotSerializer

    def get(self, request, company_id, account_id=None):
        company = resolve_administrative_company(user=request.user, company_id=company_id)

        accounts = WhatsAppBusinessAccount.objects.select_related("company", "meta_integration").filter(
            company=company,
            meta_integration__company=company,
            is_active=True,
        )

        if account_id:
            account = resolve_company_whatsapp_business_account(company=company, account_id=account_id)
            response_payload = {"success_message": "Cuenta de WhatsApp Business extraída correctamente.", "data": self.business_serializer(account, context={"company": company}).data}
            return Response(response_payload, status=HTTP_200_OK)

        response_payload = {"success_message": "Cuentas de WhatsApp Business extraídas correctamente.", "data": self.snapshot_serializer(accounts, many=True).data}
        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request, company_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        serializer = self.business_serializer(data=request.data, context={"company": company})

        if not serializer.is_valid():
            response_payload = {"error_message": "Creación de cuenta de WhatsApp Business rechazada: los datos proporcionados no son válidos.", "data": serializer.errors}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        account = serializer.save(company=company, created_by=request.user, updated_by=request.user)
        response_payload = {"success_message": "Cuenta de WhatsApp Business creada correctamente.", "data": self.business_serializer(account, context={"company": company}).data}
        return Response(response_payload, status=HTTP_201_CREATED)

    def patch(self, request, company_id, account_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        account = resolve_company_whatsapp_business_account(company=company, account_id=account_id)
        serializer = self.business_serializer(account, data=request.data, partial=True, context={"company": company})

        if not serializer.is_valid():
            response_payload = {"error_message": "Actualización de cuenta de WhatsApp Business rechazada: los datos proporcionados no son válidos.", "data": serializer.errors}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        account = serializer.save(updated_by=request.user)
        response_payload = {"success_message": "Cuenta de WhatsApp Business actualizada correctamente.", "data": self.business_serializer(account, context={"company": company}).data}
        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id, account_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        account = resolve_company_whatsapp_business_account(company=company, account_id=account_id)

        if account.numbers.filter(company=company, is_active=True).exists():
            response_payload = {"error_message": "Desactivación de cuenta rechazada: existen números de WhatsApp activos asociados.", "data": {}}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        account.is_active = False
        account.updated_by = request.user
        account.save(update_fields=["is_active", "updated_by", "updated_at"])

        response_payload = {"success_message": "Cuenta de WhatsApp Business desactivada correctamente.", "data": self.business_serializer(account, context={"company": company}).data}
        return Response(response_payload, status=HTTP_200_OK)


class WhatsAppNumberView(APIView):
    """
        DOCSTRING: WhatsApp Number View

        Description:
        - Return active WhatsApp numbers belonging to a specific company and branch.
        - Create, partially update, and deactivate corporate WhatsApp numbers.

        Notes:
        - Company and branch identifiers are tenant-scoped.
        - The associated WABA and Meta integration must remain inside the same company.
        - Foreign number identifiers are treated as nonexistent.
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
            "whatsapp_business_account__meta_integration",
        ).filter(
            company=company,
            branch=branch,
            branch__company=company,
            whatsapp_business_account__company=company,
            whatsapp_business_account__meta_integration__company=company,
            is_active=True,
        )

        if number_id:
            whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)
            response_payload = {"success_message": "Número de WhatsApp extraído correctamente.", "data": self.business_serializer(whatsapp_number, context={"company": company}).data}
            return Response(response_payload, status=HTTP_200_OK)

        response_payload = {"success_message": "Números de WhatsApp extraídos correctamente.", "data": self.snapshot_serializer(numbers, many=True).data}
        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request, company_id, branch_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        serializer = self.business_serializer(data=request.data, context={"company": company})

        if not serializer.is_valid():
            response_payload = {"error_message": "Creación de número de WhatsApp rechazada: los datos proporcionados no son válidos.", "data": serializer.errors}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        whatsapp_number = serializer.save(company=company, branch=branch, created_by=request.user, updated_by=request.user)
        response_payload = {"success_message": "Número de WhatsApp creado correctamente.", "data": self.business_serializer(whatsapp_number, context={"company": company}).data}
        return Response(response_payload, status=HTTP_201_CREATED)

    def patch(self, request, company_id, branch_id, number_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)
        serializer = self.business_serializer(whatsapp_number, data=request.data, partial=True, context={"company": company})

        if not serializer.is_valid():
            response_payload = {"error_message": "Actualización de número de WhatsApp rechazada: los datos proporcionados no son válidos.", "data": serializer.errors}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        whatsapp_number = serializer.save(company=company, branch=branch, updated_by=request.user)
        response_payload = {"success_message": "Número de WhatsApp actualizado correctamente.", "data": self.business_serializer(whatsapp_number, context={"company": company}).data}
        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id, branch_id, number_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)

        if whatsapp_number.is_monitoring_enabled:
            response_payload = {"error_message": "Desactivación de número rechazada: el monitoreo se encuentra activo.", "data": {}}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        whatsapp_number.is_active = False
        whatsapp_number.updated_by = request.user
        whatsapp_number.save(update_fields=["is_active", "updated_by", "updated_at"])

        response_payload = {"success_message": "Número de WhatsApp desactivado correctamente.", "data": self.business_serializer(whatsapp_number, context={"company": company}).data}
        return Response(response_payload, status=HTTP_200_OK)


class WhatsAppMonitoringView(APIView):
    """
        DOCSTRING: WhatsApp Monitoring View

        Description:
        - Activate and deactivate monitored message capture for a corporate WhatsApp number.

        Notes:
        - The number is resolved through the full administrative company and branch tenant hierarchy.
        - Foreign number identifiers return not found.
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
            response_payload = {"error_message": "Activación de monitoreo rechazada: no fue posible completar la operación.", "data": error.message_dict}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        response_payload = {"success_message": "Monitoreo de WhatsApp activado correctamente.", "data": self.snapshot_serializer(whatsapp_number).data}
        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id, branch_id, number_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)

        try:
            whatsapp_number = deactivate_whatsapp_monitoring(whatsapp_number=whatsapp_number, actor=request.user)
        except ValidationError as error:
            response_payload = {"error_message": "Desactivación de monitoreo rechazada: no fue posible completar la operación.", "data": error.message_dict}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        response_payload = {"success_message": "Monitoreo de WhatsApp desactivado correctamente.", "data": self.snapshot_serializer(whatsapp_number).data}
        return Response(response_payload, status=HTTP_200_OK)


class NumberAssignmentView(APIView):
    """
        DOCSTRING: Number Assignment View

        Description:
        - Return current and historical assignments associated with a corporate WhatsApp number.
        - Assign or reassign the number to an eligible company member.
        - End the currently active assignment.

        Notes:
        - Company, branch, number, assignment, and member relationships remain tenant-scoped.
        - Historical assignments remain preserved.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = NumberAssignmentSerializer
    snapshot_serializer = NumberAssignmentSnapshotSerializer

    def get(self, request, company_id, branch_id, number_id, assignment_id=None):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)

        assignments = NumberAssignment.objects.select_related("member", "member__company", "member__branch", "member__position").filter(
            whatsapp_number=whatsapp_number,
            member__company=company,
        ).order_by("-assigned_at", "-id")

        if assignment_id:
            assignment = resolve_whatsapp_number_assignment(whatsapp_number=whatsapp_number, assignment_id=assignment_id)
            response_payload = {"success_message": "Asignación de número extraída correctamente.", "data": self.snapshot_serializer(assignment).data}
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
            response_payload = {"error_message": "Asignación de número rechazada: los datos proporcionados no son válidos.", "data": serializer.errors}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        try:
            assignment = assign_whatsapp_number(whatsapp_number=whatsapp_number, member=serializer.validated_data["member"], actor=request.user)
        except ValidationError as error:
            response_payload = {"error_message": "Asignación de número rechazada: no fue posible completar la operación.", "data": error.message_dict}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        response_payload = {"success_message": "Número de WhatsApp asignado correctamente.", "data": self.snapshot_serializer(assignment).data}
        return Response(response_payload, status=HTTP_201_CREATED)

    def delete(self, request, company_id, branch_id, number_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)

        try:
            assignment = unassign_whatsapp_number(whatsapp_number=whatsapp_number, actor=request.user)
        except ValidationError as error:
            response_payload = {"error_message": "Desasignación rechazada: no fue posible completar la operación.", "data": error.message_dict}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        response_payload = {"success_message": "Número de WhatsApp desasignado correctamente.", "data": self.snapshot_serializer(assignment).data}
        return Response(response_payload, status=HTTP_200_OK)


class ConversationView(APIView):
    """
        DOCSTRING: Conversation View

        Description:
        - Return paginated monitored conversations belonging to a corporate WhatsApp number.
        - Return detailed information for a specific monitored conversation.
        - Support search, unread filtering, current-member assignment filtering, and explicit ordering.

        Notes:
        - Only MONITOR users may access conversation content.
        - Company access is resolved first.
        - The WhatsApp number is then resolved inside that company.
        - Conversations are resolved inside that number and company.
        - Foreign conversation identifiers therefore behave as nonexistent.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitor]
    business_serializer = ConversationSerializer
    snapshot_serializer = ConversationSnapshotSerializer
    pagination_class = ConversationPagination

    def get(self, request, company_id, branch_id, number_id, conversation_id=None):
        company_access = resolve_user_company_access(user=request.user, company_id=company_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company_access.company, branch_id=branch_id, number_id=number_id)
        current_assignment = get_current_whatsapp_number_assignment(whatsapp_number=whatsapp_number)

        if conversation_id:
            conversation = resolve_whatsapp_number_conversation(whatsapp_number=whatsapp_number, conversation_id=conversation_id)

            response_payload = {
                "success_message": "Conversación extraída correctamente.",
                "data": self.business_serializer(conversation, context={"request": request, "current_assignment": current_assignment}).data,
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
            whatsapp_number__company=company_access.company,
            customer__company=company_access.company,
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
                conversations = conversations.filter(read_states__user=request.user, read_states__is_read=False, read_states__unread_count__gt=0)

            elif normalized_unread in ["false", "0", "no"]:
                conversations = conversations.filter(
                    Q(read_states__user=request.user, read_states__is_read=True)
                    | Q(read_states__user=request.user, read_states__unread_count=0)
                    | ~Q(read_states__user=request.user)
                )

            else:
                response_payload = {"error_message": "Filtro de conversaciones rechazado: unread contiene un valor inválido.", "data": {"unread": "Valores permitidos: true, false, 1, 0, yes, no."}}
                return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        if member_id is not None:
            try:
                member_id = int(member_id)
            except (TypeError, ValueError):
                response_payload = {"error_message": "Filtro de conversaciones rechazado: member_id no contiene un identificador válido.", "data": {"member_id": "Debe proporcionar un identificador numérico válido."}}
                return Response(response_payload, status=HTTP_400_BAD_REQUEST)

            if current_assignment is None or current_assignment.member_id != member_id:
                conversations = conversations.none()

        allowed_ordering = ["last_message_at", "-last_message_at", "created_at", "-created_at"]

        if ordering not in allowed_ordering:
            response_payload = {"error_message": "Ordenamiento de conversaciones rechazado: el criterio proporcionado no es válido.", "data": {"ordering": f"Valores permitidos: {', '.join(allowed_ordering)}."}}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        conversations = conversations.order_by(ordering, "-id").distinct()
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(conversations, request, view=self)

        for conversation in page:
            conversation.current_user_read_state = conversation.current_user_read_states[0] if conversation.current_user_read_states else None

        response_data = self.snapshot_serializer(page, many=True, context={"request": request, "current_assignment": current_assignment}).data
        return paginator.get_paginated_response(response_data)


class ConversationReadView(APIView):
    """
        DOCSTRING: Conversation Read View

        Description:
        - Mark a monitored conversation as read for the authenticated monitoring user.

        Notes:
        - Company, number, and conversation resolution remain tenant-scoped.
        - A conversation belonging to another company or number cannot be marked as read.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitor]
    snapshot_serializer = ConversationReadStateSnapshotSerializer

    def post(self, request, company_id, branch_id, number_id, conversation_id):
        company_access = resolve_user_company_access(user=request.user, company_id=company_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company_access.company, branch_id=branch_id, number_id=number_id)
        conversation = resolve_whatsapp_number_conversation(whatsapp_number=whatsapp_number, conversation_id=conversation_id)
        read_state = mark_conversation_as_read(conversation=conversation, user=request.user)

        response_payload = {"success_message": "Conversación marcada como leída correctamente.", "data": self.snapshot_serializer(read_state).data}
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
    permission_classes = [IsAuthenticated, IsMonitor]
    business_serializer = MessageSerializer
    pagination_class = MessagePagination

    def get(self, request, company_id, branch_id, number_id, conversation_id, message_id=None):
        company_access = resolve_user_company_access(user=request.user, company_id=company_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company_access.company, branch_id=branch_id, number_id=number_id)
        conversation = resolve_whatsapp_number_conversation(whatsapp_number=whatsapp_number, conversation_id=conversation_id)

        messages = Message.objects.select_related("context_message", "conversation").prefetch_related("media_attachments").filter(
            conversation=conversation,
            conversation__whatsapp_number=whatsapp_number,
            conversation__customer__company=company_access.company,
            is_active=True,
        )

        if message_id:
            message = resolve_conversation_message(conversation=conversation, message_id=message_id)
            response_payload = {"success_message": "Mensaje extraído correctamente.", "data": self.business_serializer(message).data}
            return Response(response_payload, status=HTTP_200_OK)

        ordering = request.query_params.get("ordering", "message_timestamp")
        allowed_ordering = ["message_timestamp", "-message_timestamp"]

        if ordering not in allowed_ordering:
            response_payload = {"error_message": "Ordenamiento de mensajes rechazado: el criterio proporcionado no es válido.", "data": {"ordering": f"Valores permitidos: {', '.join(allowed_ordering)}."}}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        messages = messages.order_by(ordering, "id" if ordering == "message_timestamp" else "-id")
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
    permission_classes = [IsAuthenticated, IsMonitor]
    business_serializer = MediaAttachmentSerializer
    snapshot_serializer = MediaAttachmentSnapshotSerializer

    def get(self, request, company_id, branch_id, number_id, conversation_id, message_id, attachment_id=None):
        company_access = resolve_user_company_access(user=request.user, company_id=company_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company_access.company, branch_id=branch_id, number_id=number_id)
        conversation = resolve_whatsapp_number_conversation(whatsapp_number=whatsapp_number, conversation_id=conversation_id)
        message = resolve_conversation_message(conversation=conversation, message_id=message_id)

        attachments = MediaAttachment.objects.filter(message=message, message__conversation=conversation, is_active=True)

        if attachment_id:
            attachment = resolve_message_media_attachment(message=message, attachment_id=attachment_id)
            response_payload = {"success_message": "Adjunto multimedia extraído correctamente.", "data": self.business_serializer(attachment).data}
            return Response(response_payload, status=HTTP_200_OK)

        response_payload = {"success_message": "Adjuntos multimedia extraídos correctamente.", "data": self.snapshot_serializer(attachments, many=True).data}
        return Response(response_payload, status=HTTP_200_OK)


class MetaWebhookView(APIView):
    """
        DOCSTRING: Meta Webhook View

        Description:
        - Provide the public webhook endpoint used by Meta for WhatsApp verification and event delivery.
        - Authenticate Meta requests synchronously.
        - Queue validated webhook payloads for asynchronous persistence.

        Notes:
        - This endpoint does not require CentralChat authentication.
        - webhook_key identifies the owning Meta integration.
        - GET verification remains synchronous because Meta requires the challenge response.
        - POST signature validation remains synchronous because untrusted payloads must never enter the task broker.
        - Successfully authenticated POST payloads are queued through Celery.
        - Sensitive Meta credentials are never passed to Celery.
        - The HTTP request returns immediately after successful queue publication.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, webhook_key):
        mode = request.query_params.get("hub.mode")
        supplied_verify_token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if not mode or not supplied_verify_token or challenge is None:
            response_payload = {"error_message": "Verificación de webhook rechazada: los parámetros requeridos no fueron proporcionados.", "data": {}}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        integration = get_object_or_404(
            MetaIntegration.objects.select_related("company"),
            webhook_key=webhook_key,
            company__is_active=True,
            is_active=True,
        )

        try:
            credentials = get_meta_credentials(integration.credential_reference)
        except ImproperlyConfigured:
            response_payload = {"error_message": "Verificación de webhook rechazada: la integración de Meta no se encuentra correctamente configurada.", "data": {}}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        expected_verify_token = credentials["verify_token"]

        if mode != "subscribe":
            response_payload = {"error_message": "Verificación de webhook rechazada: el modo de verificación no es válido.", "data": {}}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        if not secrets.compare_digest(supplied_verify_token, expected_verify_token):
            response_payload = {"error_message": "Verificación de webhook rechazada: el token de verificación no es válido.", "data": {}}
            return Response(response_payload, status=HTTP_403_FORBIDDEN)

        return HttpResponse(challenge, status=HTTP_200_OK, content_type="text/plain")

    def post(self, request, webhook_key):
        integration = get_object_or_404(
            MetaIntegration.objects.select_related("company"),
            webhook_key=webhook_key,
            company__is_active=True,
            is_active=True,
        )

        try:
            credentials = get_meta_credentials(integration.credential_reference)
        except ImproperlyConfigured:
            response_payload = {"error_message": "Recepción de webhook rechazada: la integración de Meta no se encuentra correctamente configurada.", "data": {}}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        signature_header = request.headers.get("X-Hub-Signature-256")

        if not signature_header:
            response_payload = {"error_message": "Recepción de webhook rechazada: la firma de Meta no fue proporcionada.", "data": {}}
            return Response(response_payload, status=HTTP_403_FORBIDDEN)

        expected_signature = "sha256=" + hmac.new(credentials["app_secret"].encode("utf-8"), request.body, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(signature_header, expected_signature):
            response_payload = {"error_message": "Recepción de webhook rechazada: la firma de Meta no es válida.", "data": {}}
            return Response(response_payload, status=HTTP_403_FORBIDDEN)

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            response_payload = {"error_message": "Recepción de webhook rechazada: el contenido recibido no contiene JSON válido.", "data": {}}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        try:
            task = process_whatsapp_webhook_task.delay(integration.id, payload)
        except Exception:
            response_payload = {"error_message": "Recepción de webhook rechazada: no fue posible colocar el evento en procesamiento.", "data": {}}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        response_payload = {"success_message": "Webhook de Meta recibido correctamente.", "data": {"accepted": True, "task_id": task.id}}
        return Response(response_payload, status=HTTP_200_OK)


class OutboundMessageView(APIView):
    """
        DOCSTRING: Outbound Message View

        Description:
        - Send a plain-text WhatsApp message from a monitored CentralChat conversation.

        Notes:
        - The authenticated user must have active access to the requested company.
        - Number and conversation are resolved inside that company tenant.
        - Destination and source phone numbers are never accepted from request data.
        - A foreign conversation identifier cannot be used to send through another tenant.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitor]
    input_serializer = OutboundTextMessageSerializer
    output_serializer = MessageSerializer

    def post(self, request, company_id, branch_id, number_id, conversation_id):
        company_access = resolve_user_company_access(user=request.user, company_id=company_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company_access.company, branch_id=branch_id, number_id=number_id)
        conversation = resolve_whatsapp_number_conversation(whatsapp_number=whatsapp_number, conversation_id=conversation_id)
        serializer = self.input_serializer(data=request.data)

        if not serializer.is_valid():
            response_payload = {"error_message": "Envío de mensaje rechazado: los datos proporcionados no son válidos.", "data": serializer.errors}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        try:
            result = send_outbound_whatsapp_text_message(conversation=conversation, text_body=serializer.validated_data["text_body"], actor=request.user)
        except ValidationError as error:
            response_payload = {"error_message": "Envío de mensaje rechazado: no fue posible completar la operación.", "data": error.message_dict}
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

        response_payload = {"success_message": "Mensaje enviado a Meta correctamente.", "data": self.output_serializer(message).data}
        return Response(response_payload, status=HTTP_201_CREATED)