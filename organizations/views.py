from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView
from access.permissions import IsMonitor
from .models import Branch, Company, UserCompanyAccess
from .permissions import IsOrganizationAdministrator
from .serializers.business import BranchSerializer, CompanySerializer, UserCompanyAccessSerializer
from .serializers.snapshots import BranchSnapshotSerializer, CompanySnapshotSerializer, UserCompanyAccessSnapshotSerializer

# Define your views here.

class CompanyView(APIView):
    """
        DOCSTRING: Company View

        Description:
        - Return active companies created by the authenticated administrative user.
        - Create, partially update, and deactivate company records owned by the authenticated user.

        Notes:
        - Companies are scoped through created_by.
        - Only active companies are visible through the organizational API.
        - Users must not retrieve or modify companies created by another administrative user.
        - Company records are deactivated instead of destructively deleted.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = CompanySerializer
    snapshot_serializer = CompanySnapshotSerializer

    def get(self, request, company_id=None):
        companies = Company.objects.filter(created_by=request.user, is_active=True)
        if company_id:
            company = get_object_or_404(companies, id=company_id)
            success_message = "Empresa extraída correctamente."
            response_data = self.business_serializer(company).data
            response_payload = {"success_message": success_message, "data": response_data}
            return Response(response_payload, status=HTTP_200_OK)
        success_message = "Empresas extraídas correctamente."
        response_data = self.snapshot_serializer(companies, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request):
        serializer = self.business_serializer(data=request.data)
        if not serializer.is_valid():
            error_message = "Creación de empresa rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        company = serializer.save(created_by=request.user, updated_by=request.user)
        success_message = "Empresa creada correctamente."
        response_data = self.business_serializer(company).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_201_CREATED)

    def patch(self, request, company_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        serializer = self.business_serializer(company, data=request.data, partial=True)
        if not serializer.is_valid():
            error_message = "Actualización de empresa rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        company = serializer.save(updated_by=request.user)
        success_message = "Empresa actualizada correctamente."
        response_data = self.business_serializer(company).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        company.is_active = False
        company.updated_by = request.user
        company.save(update_fields=["is_active", "updated_by", "updated_at"])
        success_message = "Empresa desactivada correctamente."
        response_data = self.business_serializer(company).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)


class BranchView(APIView):
    """
        DOCSTRING: Branch View

        Description:
        - Return branches belonging to a specific active company owned by the authenticated administrative user.
        - Create, partially update, and deactivate branch records within the specified company.

        Notes:
        - The company identifier is required for every branch operation.
        - The parent company must belong to the authenticated user and remain active.
        - Branches must not be accessed outside their parent company context.
        - Branch records are deactivated instead of destructively deleted.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = BranchSerializer
    snapshot_serializer = BranchSnapshotSerializer

    def get(self, request, company_id, branch_id=None):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        branches = Branch.objects.select_related("company").filter(company=company, is_active=True)
        if branch_id:
            branch = get_object_or_404(branches, id=branch_id)
            success_message = "Sucursal extraída correctamente."
            response_data = self.business_serializer(branch).data
            response_payload = {"success_message": success_message, "data": response_data}
            return Response(response_payload, status=HTTP_200_OK)
        success_message = "Sucursales extraídas correctamente."
        response_data = self.snapshot_serializer(branches, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request, company_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        request_data = request.data.copy()
        request_data["company"] = company.id
        serializer = self.business_serializer(data=request_data)
        if not serializer.is_valid():
            error_message = "Creación de sucursal rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        branch = serializer.save(company=company, created_by=request.user, updated_by=request.user)
        success_message = "Sucursal creada correctamente."
        response_data = self.business_serializer(branch).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_201_CREATED)

    def patch(self, request, company_id, branch_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        branch = get_object_or_404(Branch, id=branch_id, company=company, is_active=True)
        request_data = request.data.copy()
        request_data["company"] = company.id
        serializer = self.business_serializer(branch, data=request_data, partial=True)
        if not serializer.is_valid():
            error_message = "Actualización de sucursal rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        branch = serializer.save(company=company, updated_by=request.user)
        success_message = "Sucursal actualizada correctamente."
        response_data = self.business_serializer(branch).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id, branch_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        branch = get_object_or_404(Branch, id=branch_id, company=company, is_active=True)
        branch.is_active = False
        branch.updated_by = request.user
        branch.save(update_fields=["is_active", "updated_by", "updated_at"])
        success_message = "Sucursal desactivada correctamente."
        response_data = self.business_serializer(branch).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)


class UserCompanyAccessView(APIView):
    """
        DOCSTRING: User Company Access View

        Description:
        - Return company access records associated with active companies created by the authenticated administrative user.
        - Grant and revoke MONITOR access only for active companies owned by the authenticated user.

        Notes:
        - Access records are scoped through company ownership.
        - Only access records associated with active companies are visible.
        - Users must not retrieve, grant, or revoke access for companies created by another administrative user.
        - Revocation deactivates the access record instead of deleting it.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = UserCompanyAccessSerializer
    snapshot_serializer = UserCompanyAccessSnapshotSerializer

    def get(self, request, access_id=None):
        accesses = UserCompanyAccess.objects.select_related("user", "company").filter(company__created_by=request.user, company__is_active=True)
        if access_id:
            access = get_object_or_404(accesses, id=access_id)
            success_message = "Acceso de empresa extraído correctamente."
            response_data = self.snapshot_serializer(access).data
            response_payload = {"success_message": success_message, "data": response_data}
            return Response(response_payload, status=HTTP_200_OK)
        success_message = "Accesos de empresa extraídos correctamente."
        response_data = self.snapshot_serializer(accesses, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request):
        serializer = self.business_serializer(data=request.data)
        if not serializer.is_valid():
            error_message = "Asignación de acceso rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        company = serializer.validated_data["company"]
        if company.created_by_id != request.user.id:
            error_message = "Asignación de acceso rechazada: la empresa seleccionada no pertenece al usuario autenticado."
            response_data = {}
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        if not company.is_active:
            error_message = "Asignación de acceso rechazada: la empresa seleccionada se encuentra inactiva."
            response_data = {}
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        access = serializer.save(created_by=request.user, updated_by=request.user)
        success_message = "Acceso de empresa asignado correctamente."
        response_data = self.snapshot_serializer(access).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_201_CREATED)

    def delete(self, request, access_id):
        access = get_object_or_404(UserCompanyAccess, id=access_id, company__created_by=request.user, company__is_active=True, is_active=True)
        access.is_active = False
        access.revoked_at = timezone.now()
        access.updated_by = request.user
        access.save(update_fields=["is_active", "revoked_at", "updated_by", "updated_at"])
        success_message = "Acceso de empresa revocado correctamente."
        response_data = self.snapshot_serializer(access).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)


class MyCompanyListView(APIView):
    """
        DOCSTRING: My Company List View

        Description:
        - Return active companies explicitly assigned to the authenticated MONITOR user.

        Notes:
        - Only active companies with an active UserCompanyAccess record are returned.
        - Company visibility is resolved exclusively through company access records.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitor]
    snapshot_serializer = CompanySnapshotSerializer

    def get(self, request):
        companies = Company.objects.filter(user_accesses__user=request.user, user_accesses__is_active=True, is_active=True).distinct()
        success_message = "Empresas autorizadas extraídas correctamente."
        response_data = self.snapshot_serializer(companies, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)