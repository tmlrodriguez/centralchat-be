from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView
from access.permissions import IsMonitor
from organizations.models import Branch, Company, UserCompanyAccess, UserCompanyAccess
from organizations.permissions import IsOrganizationAdministrator
from .models import NumberAssignment, WhatsAppBusinessAccount, WhatsAppNumber
from .operations import activate_whatsapp_monitoring, assign_whatsapp_number, deactivate_whatsapp_monitoring, unassign_whatsapp_number
from .serializers.business import NumberAssignmentSerializer, WhatsAppBusinessAccountSerializer, WhatsAppNumberSerializer, ConversationSerializer, MediaAttachmentSerializer, MessageSerializer
from .serializers.snapshots import NumberAssignmentSnapshotSerializer, WhatsAppBusinessAccountSnapshotSerializer, WhatsAppNumberSnapshotSerializer, ConversationReadStateSnapshotSerializer, ConversationSnapshotSerializer, MediaAttachmentSnapshotSerializer, MessageSnapshotSerializer
from .models import Conversation, ConversationReadState, MediaAttachment, Message, WhatsAppNumber
from .operations import mark_conversation_as_read

# Define your views here.

class WhatsAppBusinessAccountView(APIView):
    """
        DOCSTRING: WhatsApp Business Account View

        Description:
        - Return active WhatsApp Business Accounts belonging to a specific active company.
        - Create, partially update, and deactivate WhatsApp Business Account records.

        Notes:
        - The company identifier is required for every operation.
        - The company must belong to the authenticated administrative user and remain active.
        - WhatsApp Business Account records are deactivated instead of destructively deleted.
        - Integration credentials must not be exposed through API responses.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = WhatsAppBusinessAccountSerializer
    snapshot_serializer = WhatsAppBusinessAccountSnapshotSerializer

    def get(self, request, company_id, account_id=None):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        accounts = WhatsAppBusinessAccount.objects.filter(company=company, is_active=True)
        if account_id:
            account = get_object_or_404(accounts, id=account_id)
            success_message = "Cuenta de WhatsApp Business extraída correctamente."
            response_data = self.business_serializer(account).data
            response_payload = {"success_message": success_message, "data": response_data}
            return Response(response_payload, status=HTTP_200_OK)
        success_message = "Cuentas de WhatsApp Business extraídas correctamente."
        response_data = self.snapshot_serializer(accounts, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request, company_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        serializer = self.business_serializer(data=request.data)
        if not serializer.is_valid():
            error_message = "Creación de cuenta de WhatsApp Business rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        account = serializer.save(company=company, created_by=request.user, updated_by=request.user)
        success_message = "Cuenta de WhatsApp Business creada correctamente."
        response_data = self.business_serializer(account).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_201_CREATED)

    def patch(self, request, company_id, account_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        account = get_object_or_404(WhatsAppBusinessAccount, id=account_id, company=company, is_active=True)
        serializer = self.business_serializer(account, data=request.data, partial=True)
        if not serializer.is_valid():
            error_message = "Actualización de cuenta de WhatsApp Business rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        account = serializer.save(updated_by=request.user)
        success_message = "Cuenta de WhatsApp Business actualizada correctamente."
        response_data = self.business_serializer(account).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id, account_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        account = get_object_or_404(WhatsAppBusinessAccount, id=account_id, company=company, is_active=True)
        account.is_active = False
        account.updated_by = request.user
        account.save(update_fields=["is_active", "updated_by", "updated_at"])
        success_message = "Cuenta de WhatsApp Business desactivada correctamente."
        response_data = self.business_serializer(account).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)


class WhatsAppNumberView(APIView):
    """
        DOCSTRING: WhatsApp Number View

        Description:
        - Return active WhatsApp numbers belonging to a specific active branch of an active company.
        - Create, partially update, and deactivate corporate WhatsApp numbers.

        Notes:
        - Company and branch identifiers are required.
        - The company must belong to the authenticated administrative user.
        - The branch must belong to the supplied company and remain active.
        - The selected WhatsApp Business Account must belong to the same company.
        - Monitoring lifecycle fields are controlled separately from normal number configuration.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = WhatsAppNumberSerializer
    snapshot_serializer = WhatsAppNumberSnapshotSerializer

    def get(self, request, company_id, branch_id, number_id=None):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        branch = get_object_or_404(Branch, id=branch_id, company=company, is_active=True)
        numbers = WhatsAppNumber.objects.select_related("company", "branch", "whatsapp_business_account").filter(company=company, branch=branch, is_active=True)
        if number_id:
            whatsapp_number = get_object_or_404(numbers, id=number_id)
            success_message = "Número de WhatsApp extraído correctamente."
            response_data = self.business_serializer(whatsapp_number, context={"company": company}).data
            response_payload = {"success_message": success_message, "data": response_data}
            return Response(response_payload, status=HTTP_200_OK)
        success_message = "Números de WhatsApp extraídos correctamente."
        response_data = self.snapshot_serializer(numbers, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request, company_id, branch_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        branch = get_object_or_404(Branch, id=branch_id, company=company, is_active=True)
        serializer = self.business_serializer(data=request.data, context={"company": company})
        if not serializer.is_valid():
            error_message = "Creación de número de WhatsApp rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        whatsapp_number = serializer.save(company=company, branch=branch, created_by=request.user, updated_by=request.user)
        success_message = "Número de WhatsApp creado correctamente."
        response_data = self.business_serializer(whatsapp_number, context={"company": company}).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_201_CREATED)

    def patch(self, request, company_id, branch_id, number_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        branch = get_object_or_404(Branch, id=branch_id, company=company, is_active=True)
        whatsapp_number = get_object_or_404(WhatsAppNumber, id=number_id, company=company, branch=branch, is_active=True)
        serializer = self.business_serializer(whatsapp_number, data=request.data, partial=True, context={"company": company})
        if not serializer.is_valid():
            error_message = "Actualización de número de WhatsApp rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        whatsapp_number = serializer.save(company=company, branch=branch, updated_by=request.user)
        success_message = "Número de WhatsApp actualizado correctamente."
        response_data = self.business_serializer(whatsapp_number, context={"company": company}).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id, branch_id, number_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        branch = get_object_or_404(Branch, id=branch_id, company=company, is_active=True)
        whatsapp_number = get_object_or_404(WhatsAppNumber, id=number_id, company=company, branch=branch, is_active=True)
        if whatsapp_number.is_monitoring_enabled:
            error_message = "Desactivación de número rechazada: el monitoreo se encuentra activo."
            response_data = {}
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        whatsapp_number.is_active = False
        whatsapp_number.updated_by = request.user
        whatsapp_number.save(update_fields=["is_active", "updated_by", "updated_at"])
        success_message = "Número de WhatsApp desactivado correctamente."
        response_data = self.business_serializer(whatsapp_number, context={"company": company}).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)


class WhatsAppMonitoringView(APIView):
    """
        DOCSTRING: WhatsApp Monitoring View

        Description:
        - Activate and deactivate monitored message capture for a corporate WhatsApp number.

        Notes:
        - Company, branch, and WhatsApp number identifiers are required.
        - The number must belong to the supplied active company and branch.
        - Monitoring lifecycle changes are executed through transactional operation functions.
        - Monitoring activation establishes monitoring_started_at.
        - Monitoring deactivation establishes monitoring_stopped_at.
        - Previously captured monitored messages remain preserved after deactivation.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    snapshot_serializer = WhatsAppNumberSnapshotSerializer

    def post(self, request, company_id, branch_id, number_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        branch = get_object_or_404(Branch, id=branch_id, company=company, is_active=True)
        whatsapp_number = get_object_or_404(WhatsAppNumber, id=number_id, company=company, branch=branch, is_active=True)
        try:
            whatsapp_number = activate_whatsapp_monitoring(whatsapp_number=whatsapp_number, actor=request.user)
        except ValidationError as error:
            error_message = "Activación de monitoreo rechazada: no fue posible completar la operación."
            response_data = error.message_dict
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        success_message = "Monitoreo de WhatsApp activado correctamente."
        response_data = self.snapshot_serializer(whatsapp_number).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id, branch_id, number_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        branch = get_object_or_404(Branch, id=branch_id, company=company, is_active=True)
        whatsapp_number = get_object_or_404(WhatsAppNumber, id=number_id, company=company, branch=branch, is_active=True)
        try:
            whatsapp_number = deactivate_whatsapp_monitoring(whatsapp_number=whatsapp_number, actor=request.user)
        except ValidationError as error:
            error_message = "Desactivación de monitoreo rechazada: no fue posible completar la operación."
            response_data = error.message_dict
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        success_message = "Monitoreo de WhatsApp desactivado correctamente."
        response_data = self.snapshot_serializer(whatsapp_number).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)


class NumberAssignmentView(APIView):
    """
        DOCSTRING: Number Assignment View

        Description:
        - Return the historical assignments associated with a corporate WhatsApp number.
        - Assign or reassign the number to an eligible company member.
        - End the currently active assignment.

        Notes:
        - Company, branch, and WhatsApp number identifiers are required.
        - Assignment history must remain preserved.
        - Assigned members must belong to the same company and branch as the WhatsApp number.
        - Assignment and reassignment are executed through atomic operation functions.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = NumberAssignmentSerializer
    snapshot_serializer = NumberAssignmentSnapshotSerializer

    def get(self, request, company_id, branch_id, number_id, assignment_id=None):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        branch = get_object_or_404(Branch, id=branch_id, company=company, is_active=True)
        whatsapp_number = get_object_or_404(WhatsAppNumber, id=number_id, company=company, branch=branch, is_active=True)
        assignments = NumberAssignment.objects.select_related("member").filter(whatsapp_number=whatsapp_number)
        if assignment_id:
            assignment = get_object_or_404(assignments, id=assignment_id)
            success_message = "Asignación de número extraída correctamente."
            response_data = self.snapshot_serializer(assignment).data
            response_payload = {"success_message": success_message, "data": response_data}
            return Response(response_payload, status=HTTP_200_OK)
        success_message = "Historial de asignaciones extraído correctamente."
        response_data = self.snapshot_serializer(assignments, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request, company_id, branch_id, number_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        branch = get_object_or_404(Branch, id=branch_id, company=company, is_active=True)
        whatsapp_number = get_object_or_404(WhatsAppNumber, id=number_id, company=company, branch=branch, is_active=True)
        serializer = self.business_serializer(data=request.data, context={"whatsapp_number": whatsapp_number})
        if not serializer.is_valid():
            error_message = "Asignación de número rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        try:
            assignment = assign_whatsapp_number(whatsapp_number=whatsapp_number, member=serializer.validated_data["member"], actor=request.user)
        except ValidationError as error:
            error_message = "Asignación de número rechazada: no fue posible completar la operación."
            response_data = error.message_dict
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        success_message = "Número de WhatsApp asignado correctamente."
        response_data = self.snapshot_serializer(assignment).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_201_CREATED)

    def delete(self, request, company_id, branch_id, number_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        branch = get_object_or_404(Branch, id=branch_id, company=company, is_active=True)
        whatsapp_number = get_object_or_404(WhatsAppNumber, id=number_id, company=company, branch=branch, is_active=True)
        try:
            assignment = unassign_whatsapp_number(whatsapp_number=whatsapp_number, actor=request.user)
        except ValidationError as error:
            error_message = "Desasignación rechazada: no fue posible completar la operación."
            response_data = error.message_dict
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        success_message = "Número de WhatsApp desasignado correctamente."
        response_data = self.snapshot_serializer(assignment).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)


class ConversationView(APIView):
    """
        DOCSTRING: Conversation View

        Description:
        - Return monitored conversations belonging to a specific corporate WhatsApp number.
        - Return detailed information for a specific monitored conversation.

        Notes:
        - Only MONITOR users may access conversation content.
        - The authenticated monitoring user must have active access to the company owning the WhatsApp number.
        - Administrative users must not retrieve conversation content.
        - Conversation data is read-only through this endpoint.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitor]
    business_serializer = ConversationSerializer
    snapshot_serializer = ConversationSnapshotSerializer

    def get(self, request, company_id, branch_id, number_id, conversation_id=None):
        company_access = get_object_or_404(UserCompanyAccess, user=request.user, company_id=company_id, is_active=True, company__is_active=True)
        whatsapp_number = get_object_or_404(WhatsAppNumber, id=number_id, company=company_access.company, branch_id=branch_id, branch__is_active=True, is_active=True)
        if conversation_id:
            conversation = get_object_or_404(
                Conversation.objects.select_related("customer", "last_message"),
                id=conversation_id,
                whatsapp_number=whatsapp_number,
                is_active=True,
            )
            success_message = "Conversación extraída correctamente."
            response_data = self.business_serializer(conversation).data
            response_payload = {"success_message": success_message, "data": response_data}
            return Response(response_payload, status=HTTP_200_OK)
        conversations = list(
            Conversation.objects.select_related(
                "customer",
                "last_message",
            ).prefetch_related(
                Prefetch(
                    "read_states",
                    queryset=ConversationReadState.objects.filter(user=request.user),
                    to_attr="current_user_read_states",
                )
            ).filter(
                whatsapp_number=whatsapp_number,
                is_active=True,
            )
        )
        for conversation in conversations:
            conversation.current_user_read_state = conversation.current_user_read_states[0] if conversation.current_user_read_states else None
        success_message = "Conversaciones extraídas correctamente."
        response_data = self.snapshot_serializer(conversations, many=True, context={"request": request}).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)


class ConversationReadView(APIView):
    """
        DOCSTRING: Conversation Read View

        Description:
        - Mark a monitored conversation as read for the authenticated monitoring user.

        Notes:
        - Only MONITOR users may modify their own conversation read state.
        - The authenticated user must have active company access.
        - Marking a conversation as read does not affect other monitoring users.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitor]
    snapshot_serializer = ConversationReadStateSnapshotSerializer

    def post(self, request, company_id, branch_id, number_id, conversation_id):
        company_access = get_object_or_404(UserCompanyAccess, user=request.user, company_id=company_id, is_active=True, company__is_active=True)
        whatsapp_number = get_object_or_404(WhatsAppNumber, id=number_id, company=company_access.company, branch_id=branch_id, branch__is_active=True, is_active=True)
        conversation = get_object_or_404(Conversation, id=conversation_id, whatsapp_number=whatsapp_number, is_active=True)
        read_state = mark_conversation_as_read(conversation=conversation, user=request.user)
        success_message = "Conversación marcada como leída correctamente."
        response_data = self.snapshot_serializer(read_state).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)


class MessageView(APIView):
    """
        DOCSTRING: Message View

        Description:
        - Return persisted monitored messages belonging to a specific conversation.
        - Return detailed information for a specific monitored message.

        Notes:
        - Only MONITOR users may access message content.
        - The authenticated user must have active access to the corresponding company.
        - Messages are read-only through this endpoint.
        - Historical messages remain accessible when monitoring is later deactivated.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitor]
    business_serializer = MessageSerializer
    snapshot_serializer = MessageSnapshotSerializer

    def get(self, request, company_id, branch_id, number_id, conversation_id, message_id=None):
        company_access = get_object_or_404(UserCompanyAccess, user=request.user, company_id=company_id, is_active=True, company__is_active=True)
        whatsapp_number = get_object_or_404(WhatsAppNumber, id=number_id, company=company_access.company, branch_id=branch_id, branch__is_active=True, is_active=True)
        conversation = get_object_or_404(Conversation, id=conversation_id, whatsapp_number=whatsapp_number, is_active=True)
        messages = Message.objects.prefetch_related("media_attachments").filter(conversation=conversation, is_active=True)
        if message_id:
            message = get_object_or_404(messages, id=message_id)
            success_message = "Mensaje extraído correctamente."
            response_data = self.business_serializer(message).data
            response_payload = {"success_message": success_message, "data": response_data}
            return Response(response_payload, status=HTTP_200_OK)
        success_message = "Mensajes extraídos correctamente."
        response_data = self.business_serializer(messages, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)


class MediaAttachmentView(APIView):
    """
        DOCSTRING: Media Attachment View

        Description:
        - Return media attachment metadata belonging to a monitored WhatsApp message.

        Notes:
        - Only MONITOR users may access media attachment information.
        - The authenticated user must have active company access.
        - Internal object-storage keys are never exposed.
        - Binary media delivery will be implemented separately using authorized signed URLs.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitor]
    business_serializer = MediaAttachmentSerializer
    snapshot_serializer = MediaAttachmentSnapshotSerializer

    def get(self, request, company_id, branch_id, number_id, conversation_id, message_id, attachment_id=None):
        company_access = get_object_or_404(UserCompanyAccess, user=request.user, company_id=company_id, is_active=True, company__is_active=True)
        whatsapp_number = get_object_or_404(WhatsAppNumber, id=number_id, company=company_access.company, branch_id=branch_id, branch__is_active=True, is_active=True)
        conversation = get_object_or_404(Conversation, id=conversation_id, whatsapp_number=whatsapp_number, is_active=True)
        message = get_object_or_404(Message, id=message_id, conversation=conversation, is_active=True)
        attachments = MediaAttachment.objects.filter(message=message, is_active=True)
        if attachment_id:
            attachment = get_object_or_404(attachments, id=attachment_id)
            success_message = "Adjunto multimedia extraído correctamente."
            response_data = self.business_serializer(attachment).data
            response_payload = {"success_message": success_message, "data": response_data}
            return Response(response_payload, status=HTTP_200_OK)
        success_message = "Adjuntos multimedia extraídos correctamente."
        response_data = self.snapshot_serializer(attachments, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)