from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK
from rest_framework.status import HTTP_201_CREATED
from rest_framework.status import HTTP_204_NO_CONTENT
from rest_framework.status import HTTP_400_BAD_REQUEST
from rest_framework.views import APIView
from .models import AccessUser
from .permissions import IsAdministrator, IsSuperAdministrator
from .registry import ROLE_REGISTRY
from .serializers.business import AccessUserSerializer
from .serializers.business import LoginSerializer
from .serializers.snapshots import AccessUserSnapshotSerializer


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
            error_message = "Login rejected: invalid credentials."
            response_data = serializer.errors
            response_payload = {
                "error_message": error_message,
                "data": response_data,
            }
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        token, created = Token.objects.get_or_create(user=user)
        success_message = "Login completed successfully."
        response_data = {
            "token": token.key,
            "user": self.accessuser_snapshot_serializer(user).data,
        }
        response_payload = {
            "success_message": success_message,
            "data": response_data,
        }
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
        success_message = "Logout completed successfully."
        response_data = None
        response_payload = {
            "success_message": success_message,
            "data": response_data,
        }
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
        success_message = "Current user retrieved successfully."
        response_data = self.snapshot_serializer(request.user).data
        response_payload = {
            "success_message": success_message,
            "data": response_data,
        }
        return Response(response_payload, status=HTTP_200_OK)


class AdministratorCreateView(APIView):
    """
    DOCSTRING: Administrator Create View

    Description:
    - Allow a SUPERADMINISTRATOR user to create an ADMINISTRATOR user.

    Notes:
    - The ADMINISTRATOR role is assigned exclusively by the backend.
    - Clients cannot select or override the resulting role.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsSuperAdministrator]

    business_serializer = AccessUserSerializer

    def post(self, request):
        serializer = self.business_serializer(data=request.data)
        if not serializer.is_valid():
            error_message = "Administrator creation rejected: invalid data."
            response_data = serializer.errors
            response_payload = {
                "error_message": error_message,
                "data": response_data,
            }
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        user = AccessUser.objects.create_user(role=ROLE_REGISTRY.ADMINISTRATOR, **serializer.validated_data)
        success_message = "Administrator created successfully."
        response_data = self.business_serializer(user).data
        response_payload = {
            "success_message": success_message,
            "data": response_data,
        }
        return Response(response_payload, status=HTTP_201_CREATED)


class MonitorCreateView(APIView):
    """
    DOCSTRING: Monitor Create View

    Description:
    - Allow an ADMINISTRATOR user to create a MONITOR user.

    Notes:
    - The MONITOR role is assigned exclusively by the backend.
    - Clients cannot select or override the resulting role.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsAdministrator]
    business_serializer = AccessUserSerializer

    def post(self, request):
        serializer = self.business_serializer(data=request.data)
        if not serializer.is_valid():
            error_message = "Monitor creation rejected: invalid data."
            response_data = serializer.errors
            response_payload = {
                "error_message": error_message,
                "data": response_data,
            }
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        user = AccessUser.objects.create_user(role=ROLE_REGISTRY.MONITOR, **serializer.validated_data)
        success_message = "Monitor created successfully."
        response_data = self.business_serializer(user).data
        response_payload = {
            "success_message": success_message,
            "data": response_data,
        }
        return Response(response_payload, status=HTTP_201_CREATED)