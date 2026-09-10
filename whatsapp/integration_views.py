from django.core.exceptions import ImproperlyConfigured, ValidationError
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView
from organizations.permissions import IsOrganizationAdministrator
from .integration_operations import connect_whatsapp_business_account, disconnect_whatsapp_business_account, refresh_whatsapp_business_account_state, validate_meta_integration_credentials, validate_whatsapp_number_connection
from .meta_lifecycle import MetaLifecycleAPIError
from .resolvers import resolve_administrative_company, resolve_company_branch, resolve_company_meta_integration, resolve_company_whatsapp_business_account, resolve_company_whatsapp_number
from .serializers.integration import MetaIntegrationValidationResultSerializer, WhatsAppBusinessAccountLifecycleResultSerializer, WhatsAppNumberValidationResultSerializer

# Define your views here.

def build_lifecycle_error_response(error, error_message):
    """
        DOCSTRING: Build Lifecycle Error Response

        Description:
        - Convert lifecycle validation exceptions into the standard Dialoqo API response shape.
    """

    if isinstance(error, ValidationError):
        response_data = error.message_dict if hasattr(error, "message_dict") else {"validation": error.messages}

    elif isinstance(error, MetaLifecycleAPIError):
        response_data = {
            "meta": {
                "http_status": error.http_status,
                "error_code": error.meta_error_code,
                "error_subcode": error.meta_error_subcode,
                "message": error.error_message,
            }
        }

    elif isinstance(error, ImproperlyConfigured):
        response_data = {"credentials": str(error)}

    else:
        response_data = {}

    return Response({"error_message": error_message, "data": response_data}, status=HTTP_400_BAD_REQUEST)


class MetaIntegrationValidationView(APIView):
    """
        DOCSTRING: Meta Integration Validation View

        Description:
        - Validate the stored Meta credentials for one administrative company integration.

        Notes:
        - The client cannot directly set is_connected.
        - Successful validation synchronizes the field from actual Meta authentication state.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    output_serializer = MetaIntegrationValidationResultSerializer

    def post(self, request, company_id, integration_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        integration = resolve_company_meta_integration(company=company, integration_id=integration_id)

        try:
            result = validate_meta_integration_credentials(meta_integration=integration, actor=request.user)

        except (ValidationError, MetaLifecycleAPIError, ImproperlyConfigured) as error:
            return build_lifecycle_error_response(
                error=error,
                error_message="Validación de integración rechazada: Meta no pudo validar la configuración.",
            )

        return Response(
            {
                "success_message": "Integración de Meta validada correctamente.",
                "data": self.output_serializer(result).data,
            },
            status=HTTP_200_OK,
        )


class WhatsAppBusinessAccountConnectionView(APIView):
    """
        DOCSTRING: WhatsApp Business Account Connection View

        Description:
        - Connect, refresh, and disconnect the actual Meta lifecycle of a WABA.

        Notes:
        - POST validates the WABA and subscribes the Meta app.
        - PATCH refreshes state without changing the external subscription.
        - DELETE explicitly removes the app subscription from Meta.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    output_serializer = WhatsAppBusinessAccountLifecycleResultSerializer

    def post(self, request, company_id, account_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        account = resolve_company_whatsapp_business_account(company=company, account_id=account_id)

        try:
            result = connect_whatsapp_business_account(whatsapp_business_account=account, actor=request.user)

        except (ValidationError, MetaLifecycleAPIError, ImproperlyConfigured) as error:
            return build_lifecycle_error_response(
                error=error,
                error_message="Conexión de cuenta rechazada: no fue posible conectar la WABA con Meta.",
            )

        return Response(
            {
                "success_message": "Cuenta de WhatsApp Business conectada correctamente.",
                "data": self.output_serializer(result).data,
            },
            status=HTTP_200_OK,
        )

    def patch(self, request, company_id, account_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        account = resolve_company_whatsapp_business_account(company=company, account_id=account_id)

        try:
            result = refresh_whatsapp_business_account_state(whatsapp_business_account=account, actor=request.user)

        except (ValidationError, MetaLifecycleAPIError, ImproperlyConfigured) as error:
            return build_lifecycle_error_response(
                error=error,
                error_message="Actualización de estado rechazada: no fue posible verificar la WABA contra Meta.",
            )

        return Response(
            {
                "success_message": "Estado de cuenta de WhatsApp Business actualizado correctamente.",
                "data": self.output_serializer(result).data,
            },
            status=HTTP_200_OK,
        )

    def delete(self, request, company_id, account_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        account = resolve_company_whatsapp_business_account(company=company, account_id=account_id)

        try:
            result = disconnect_whatsapp_business_account(whatsapp_business_account=account, actor=request.user)

        except (ValidationError, MetaLifecycleAPIError, ImproperlyConfigured) as error:
            return build_lifecycle_error_response(
                error=error,
                error_message="Desconexión de cuenta rechazada: no fue posible eliminar la suscripción en Meta.",
            )

        return Response(
            {
                "success_message": "Cuenta de WhatsApp Business desconectada correctamente.",
                "data": self.output_serializer(result).data,
            },
            status=HTTP_200_OK,
        )


class WhatsAppNumberValidationView(APIView):
    """
        DOCSTRING: WhatsApp Number Validation View

        Description:
        - Validate a configured Phone Number ID against the actual Meta WABA.

        Notes:
        - Company and branch boundaries are resolved before Meta validation.
        - is_connected is synchronized exclusively by this backend operation.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    output_serializer = WhatsAppNumberValidationResultSerializer

    def post(self, request, company_id, branch_id, number_id):
        company = resolve_administrative_company(user=request.user, company_id=company_id)
        branch = resolve_company_branch(company=company, branch_id=branch_id)
        whatsapp_number = resolve_company_whatsapp_number(company=company, branch_id=branch.id, number_id=number_id)

        try:
            result = validate_whatsapp_number_connection(whatsapp_number=whatsapp_number, actor=request.user)

        except (ValidationError, MetaLifecycleAPIError, ImproperlyConfigured) as error:
            return build_lifecycle_error_response(
                error=error,
                error_message="Validación de número rechazada: Meta no pudo validar el Phone Number ID.",
            )

        return Response(
            {
                "success_message": "Número de WhatsApp validado correctamente.",
                "data": self.output_serializer(result).data,
            },
            status=HTTP_200_OK,
        )