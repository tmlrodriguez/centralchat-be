from django.shortcuts import get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView
from organizations.models import Branch, Company
from organizations.permissions import IsOrganizationAdministrator
from .models import Member, Position
from .serializers.business import MemberSerializer, PositionSerializer
from .serializers.snapshots import MemberSnapshotSerializer, PositionSnapshotSerializer

# Define your views here.

class PositionView(APIView):
    """
        DOCSTRING: Position View

        Description:
        - Return active positions belonging to a specific active company owned by the authenticated administrative user.
        - Create, partially update, and deactivate company position records.

        Notes:
        - The company identifier is required for every position operation.
        - The parent company must belong to the authenticated user and remain active.
        - Position records are deactivated instead of destructively deleted.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = PositionSerializer
    snapshot_serializer = PositionSnapshotSerializer

    def get(self, request, company_id, position_id=None):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        positions = Position.objects.filter(company=company, is_active=True)
        if position_id:
            position = get_object_or_404(positions, id=position_id)
            success_message = "Posición extraída correctamente."
            response_data = self.business_serializer(position, context={"company": company}).data
            response_payload = {"success_message": success_message, "data": response_data}
            return Response(response_payload, status=HTTP_200_OK)
        success_message = "Posiciones extraídas correctamente."
        response_data = self.snapshot_serializer(positions, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request, company_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        serializer = self.business_serializer(data=request.data, context={"company": company})
        if not serializer.is_valid():
            error_message = "Creación de posición rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        position = serializer.save(company=company, created_by=request.user, updated_by=request.user)
        success_message = "Posición creada correctamente."
        response_data = self.business_serializer(position, context={"company": company}).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_201_CREATED)

    def patch(self, request, company_id, position_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        position = get_object_or_404(Position, id=position_id, company=company, is_active=True)
        serializer = self.business_serializer(position, data=request.data, partial=True, context={"company": company})
        if not serializer.is_valid():
            error_message = "Actualización de posición rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        position = serializer.save(company=company, updated_by=request.user)
        success_message = "Posición actualizada correctamente."
        response_data = self.business_serializer(position, context={"company": company}).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id, position_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        position = get_object_or_404(Position, id=position_id, company=company, is_active=True)
        position.is_active = False
        position.updated_by = request.user
        position.save(update_fields=["is_active", "updated_by", "updated_at"])
        success_message = "Posición desactivada correctamente."
        response_data = self.business_serializer(position, context={"company": company}).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)


class MemberView(APIView):
    """
        DOCSTRING: Member View

        Description:
        - Return active members belonging to a specific active company owned by the authenticated administrative user.
        - Create, partially update, and deactivate member records within the specified company.

        Notes:
        - The company identifier is required for every member operation.
        - Every member must belong to an active branch and active position of the same company.
        - Members must not be accessed outside their company context.
        - Member records are deactivated instead of destructively deleted.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = MemberSerializer
    snapshot_serializer = MemberSnapshotSerializer

    def get(self, request, company_id, member_id=None):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        members = Member.objects.select_related("company", "branch", "position").filter(company=company, is_active=True)
        if member_id:
            member = get_object_or_404(members, id=member_id)
            success_message = "Miembro extraído correctamente."
            response_data = self.business_serializer(member, context={"company": company}).data
            response_payload = {"success_message": success_message, "data": response_data}
            return Response(response_payload, status=HTTP_200_OK)
        success_message = "Miembros extraídos correctamente."
        response_data = self.snapshot_serializer(members, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def post(self, request, company_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        serializer = self.business_serializer(data=request.data, context={"company": company})
        if not serializer.is_valid():
            error_message = "Creación de miembro rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        member = serializer.save(company=company, created_by=request.user, updated_by=request.user)
        success_message = "Miembro creado correctamente."
        response_data = self.business_serializer(member, context={"company": company}).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_201_CREATED)

    def patch(self, request, company_id, member_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        member = get_object_or_404(Member, id=member_id, company=company, is_active=True)
        serializer = self.business_serializer(member, data=request.data, partial=True, context={"company": company})
        if not serializer.is_valid():
            error_message = "Actualización de miembro rechazada: los datos proporcionados no son válidos."
            response_data = serializer.errors
            response_payload = {"error_message": error_message, "data": response_data}
            return Response(response_payload, status=HTTP_400_BAD_REQUEST)
        member = serializer.save(company=company, updated_by=request.user)
        success_message = "Miembro actualizado correctamente."
        response_data = self.business_serializer(member, context={"company": company}).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)

    def delete(self, request, company_id, member_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        member = get_object_or_404(Member, id=member_id, company=company, is_active=True)
        member.is_active = False
        member.updated_by = request.user
        member.save(update_fields=["is_active", "updated_by", "updated_at"])
        success_message = "Miembro desactivado correctamente."
        response_data = self.business_serializer(member, context={"company": company}).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)


class BranchMemberView(APIView):
    """
        DOCSTRING: Branch Member View

        Description:
        - Return active members assigned to a specific active branch within an active company owned by the authenticated administrative user.

        Notes:
        - The company and branch identifiers are required.
        - The branch must belong to the supplied company.
        - Only active members are returned.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    snapshot_serializer = MemberSnapshotSerializer

    def get(self, request, company_id, branch_id):
        company = get_object_or_404(Company, id=company_id, created_by=request.user, is_active=True)
        branch = get_object_or_404(Branch, id=branch_id, company=company, is_active=True)
        members = Member.objects.select_related("company", "branch", "position").filter(company=company, branch=branch, is_active=True)
        success_message = "Miembros de sucursal extraídos correctamente."
        response_data = self.snapshot_serializer(members, many=True).data
        response_payload = {"success_message": success_message, "data": response_data}
        return Response(response_payload, status=HTTP_200_OK)