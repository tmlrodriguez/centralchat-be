from django.shortcuts import get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView
from .models import AccessUser
from .operations import create_administrator, create_monitor, deactivate_administrator, deactivate_monitor, update_administrator, update_monitor
from .permissions import IsAdministrator, IsSuperAdministrator
from .registry import ROLE_REGISTRY
from .serializers.business import AccessUserSerializer, LoginSerializer
from .serializers.snapshots import AccessUserSnapshotSerializer

# Define your views here.

class LoginView(APIView):
    """
        DOCSTRING: Login View

        Description:
        - Authenticate a CentralChat user and return a REST Framework authentication token.

        Notes:
        - The endpoint is publicly accessible.
        - A single persistent token is associated with the authenticated user.
        - Successful responses include the authentication token and an AccessUser snapshot.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    login_business_serializer = LoginSerializer
    accessuser_snapshot_serializer = AccessUserSnapshotSerializer

    def post(self, request):
        serializer = self.login_business_serializer(data=request.data)

        if not serializer.is_valid():
            error_message = "Autenticación rechazada: las credenciales proporcionadas no son válidas."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        token, created = Token.objects.get_or_create(user=user)

        success_message = "Autenticación completada correctamente."
        response_data = {"token": token.key, "user": self.accessuser_snapshot_serializer(user).data}
        response_payload = {"success_message": success_message, "data": response_data}

        return Response(response_payload, status=HTTP_200_OK)


class LogoutView(APIView):
    """
        DOCSTRING: Logout View

        Description:
        - Terminate the authenticated CentralChat token session.

        Notes:
        - Logout deletes the current authentication token.
        - A subsequent login generates a new token.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.auth.delete()

        success_message = "Sesión finalizada correctamente."
        response_data = None
        response_payload = {"success_message": success_message, "data": response_data}

        return Response(response_payload, status=HTTP_200_OK)


class CurrentUserView(APIView):
    """
        DOCSTRING: Current User View

        Description:
        - Return the currently authenticated CentralChat user.

        Notes:
        - A valid REST Framework authentication token is required.
        - The response uses the AccessUser snapshot representation.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    snapshot_serializer = AccessUserSnapshotSerializer

    def get(self, request):
        success_message = "Usuario autenticado recuperado correctamente."
        response_data = self.snapshot_serializer(request.user).data
        response_payload = {"success_message": success_message, "data": response_data}

        return Response(response_payload, status=HTTP_200_OK)


class AdministratorView(APIView):
    """
        DOCSTRING: Administrator View

        Description:
        - Allow a SUPERADMINISTRATOR user to manage ADMINISTRATOR users created by that superadministrator.
        - Return, create, partially update, and deactivate administrator records.

        Notes:
        - The ADMINISTRATOR role is controlled exclusively by the backend.
        - Administrators are scoped through created_by.
        - Foreign administrator identifiers behave as nonexistent.
        - Password changes are not supported through this endpoint.
        - Administrator mutations are delegated to the access operation layer.
        - Administrator records are deactivated instead of destructively deleted.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdministrator]
    business_serializer = AccessUserSerializer
    snapshot_serializer = AccessUserSnapshotSerializer

    def get(self, request, user_id=None):
        administrators = AccessUser.objects.filter(role=ROLE_REGISTRY.ADMINISTRATOR, created_by=request.user, is_active=True).order_by("first_name", "last_name", "username")

        if user_id:
            administrator = get_object_or_404(administrators, id=user_id)

            success_message = "Administrador extraído correctamente."
            response_data = self.business_serializer(administrator).data
            response_payload = {"success_message": success_message, "data": response_data}

            return Response(response_payload, status=HTTP_200_OK)

        success_message = "Administradores extraídos correctamente."
        response_data = self.snapshot_serializer(administrators, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}

        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request):
        serializer = self.business_serializer(data=request.data)

        if not serializer.is_valid():
            error_message = "Creación de administrador rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        administrator = create_administrator(validated_data=serializer.validated_data, actor=request.user)

        success_message = "Administrador creado correctamente."
        response_data = self.business_serializer(administrator).data
        response_payload = {"success_message": success_message, "data": response_data}

        return Response(response_payload, status=HTTP_201_CREATED)

    def patch(self, request, user_id):
        administrator = get_object_or_404(AccessUser, id=user_id, role=ROLE_REGISTRY.ADMINISTRATOR, created_by=request.user, is_active=True)

        if "password" in request.data:
            error_message = "Actualización de administrador rechazada: la contraseña no puede modificarse mediante este endpoint."
            response_data = {"password": "Utilice la operación específica de cambio de contraseña."}
            response_payload = {"error_message": error_message, "data": response_data}

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        serializer = self.business_serializer(administrator, data=request.data, partial=True)

        if not serializer.is_valid():
            error_message = "Actualización de administrador rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        administrator = update_administrator(administrator=administrator, validated_data=serializer.validated_data, actor=request.user)

        success_message = "Administrador actualizado correctamente."
        response_data = self.business_serializer(administrator).data
        response_payload = {"success_message": success_message, "data": response_data}

        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, user_id):
        administrator = get_object_or_404(AccessUser, id=user_id, role=ROLE_REGISTRY.ADMINISTRATOR, created_by=request.user, is_active=True)
        administrator = deactivate_administrator(administrator=administrator, actor=request.user)

        success_message = "Administrador desactivado correctamente."
        response_data = self.business_serializer(administrator).data
        response_payload = {"success_message": success_message, "data": response_data}

        return Response(response_payload, status=HTTP_200_OK)


class MonitorView(APIView):
    """
        DOCSTRING: Monitor View

        Description:
        - Allow an ADMINISTRATOR user to manage MONITOR users created by that administrator.
        - Return, create, partially update, and deactivate monitor records.

        Notes:
        - The MONITOR role is controlled exclusively by the backend.
        - Monitors are scoped through created_by.
        - Foreign monitor identifiers behave as nonexistent.
        - Company access remains managed through the organizations subsystem.
        - Password changes are not supported through this endpoint.
        - Monitor mutations are delegated to the access operation layer.
        - Monitor records are deactivated instead of destructively deleted.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsAdministrator]
    business_serializer = AccessUserSerializer
    snapshot_serializer = AccessUserSnapshotSerializer

    def get(self, request, user_id=None):
        monitors = AccessUser.objects.filter(role=ROLE_REGISTRY.MONITOR, created_by=request.user, is_active=True).order_by("first_name", "last_name", "username")

        if user_id:
            monitor = get_object_or_404(monitors, id=user_id)

            success_message = "Monitor extraído correctamente."
            response_data = self.business_serializer(monitor).data
            response_payload = {"success_message": success_message, "data": response_data}

            return Response(response_payload, status=HTTP_200_OK)

        success_message = "Monitores extraídos correctamente."
        response_data = self.snapshot_serializer(monitors, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}

        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request):
        serializer = self.business_serializer(data=request.data)

        if not serializer.is_valid():
            error_message = "Creación de monitor rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        monitor = create_monitor(validated_data=serializer.validated_data, actor=request.user)

        success_message = "Monitor creado correctamente."
        response_data = self.business_serializer(monitor).data
        response_payload = {"success_message": success_message, "data": response_data}

        return Response(response_payload, status=HTTP_201_CREATED)

    def patch(self, request, user_id):
        monitor = get_object_or_404(AccessUser, id=user_id, role=ROLE_REGISTRY.MONITOR, created_by=request.user, is_active=True)

        if "password" in request.data:
            error_message = "Actualización de monitor rechazada: la contraseña no puede modificarse mediante este endpoint."
            response_data = {"password": "Utilice la operación específica de cambio de contraseña."}
            response_payload = {"error_message": error_message, "data": response_data}

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        serializer = self.business_serializer(monitor, data=request.data, partial=True)

        if not serializer.is_valid():
            error_message = "Actualización de monitor rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        monitor = update_monitor(monitor=monitor, validated_data=serializer.validated_data, actor=request.user)

        success_message = "Monitor actualizado correctamente."
        response_data = self.business_serializer(monitor).data
        response_payload = {"success_message": success_message, "data": response_data}

        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, user_id):
        monitor = get_object_or_404(AccessUser, id=user_id, role=ROLE_REGISTRY.MONITOR, created_by=request.user, is_active=True)
        monitor = deactivate_monitor(monitor=monitor, actor=request.user)

        success_message = "Monitor desactivado correctamente."
        response_data = self.business_serializer(monitor).data
        response_payload = {"success_message": success_message, "data": response_data}

        return Response(response_payload, status=HTTP_200_OK)