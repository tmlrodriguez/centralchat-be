from rest_framework import serializers
from access.serializers.snapshots import AccessUserSnapshotSerializer
from organizations.serializers.snapshots import CompanySnapshotSerializer
from ..models import Member, Position

# Define your serializers here.

class PositionSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Position Serializer

        Description:
        - Serialize and validate the primary CentralChat position resource.

        Notes:
        - The company is determined from the URL and controlled exclusively by the backend.
        - Temporal and author fields are controlled exclusively by the backend.
    """
    company = CompanySnapshotSerializer(read_only=True)
    created_by = AccessUserSnapshotSerializer(read_only=True)
    updated_by = AccessUserSnapshotSerializer(read_only=True)

    class Meta:
        model = Position
        fields = ["id", "company", "name", "code", "description", "is_active", "created_at", "updated_at", "created_by", "updated_by"]
        read_only_fields = ["id", "company", "created_at", "updated_at", "created_by", "updated_by"]

    def validate_code(self, value):
        company = self.context.get("company")
        if company is None:
            raise serializers.ValidationError("Validación de posición rechazada: no se pudo determinar la empresa.")
        positions = Position.objects.filter(company=company, code=value)
        if self.instance:
            positions = positions.exclude(id=self.instance.id)
        if positions.exists():
            raise serializers.ValidationError("Validación de posición rechazada: el código ya existe en esta empresa.")
        return value


class MemberSerializer(serializers.ModelSerializer):
    """
        DOCSTRING: Member Serializer

        Description:
        - Serialize and validate the primary CentralChat member resource.

        Notes:
        - The company is determined from the URL and controlled exclusively by the backend.
        - Branch and position are required.
        - Branch and position must belong to the same active company as the member.
        - Temporal and author fields are controlled exclusively by the backend.
    """
    company = CompanySnapshotSerializer(read_only=True)
    created_by = AccessUserSnapshotSerializer(read_only=True)
    updated_by = AccessUserSnapshotSerializer(read_only=True)

    class Meta:
        model = Member
        fields = ["id", "company", "branch", "position", "member_code", "first_name", "last_name", "email", "notes", "is_active", "created_at", "updated_at", "created_by", "updated_by"]
        read_only_fields = ["id", "company", "created_at", "updated_at", "created_by", "updated_by"]

    def validate_branch(self, value):
        company = self.context.get("company")
        if company is None:
            raise serializers.ValidationError("Asignación de sucursal rechazada: no se pudo determinar la empresa.")
        if value.company_id != company.id:
            raise serializers.ValidationError("Asignación de sucursal rechazada: la sucursal seleccionada no pertenece a la empresa.")
        if not value.is_active:
            raise serializers.ValidationError("Asignación de sucursal rechazada: la sucursal seleccionada se encuentra inactiva.")
        return value

    def validate_position(self, value):
        company = self.context.get("company")
        if company is None:
            raise serializers.ValidationError("Asignación de posición rechazada: no se pudo determinar la empresa.")
        if value.company_id != company.id:
            raise serializers.ValidationError("Asignación de posición rechazada: la posición seleccionada no pertenece a la empresa.")
        if not value.is_active:
            raise serializers.ValidationError("Asignación de posición rechazada: la posición seleccionada se encuentra inactiva.")
        return value

    def validate_member_code(self, value):
        company = self.context.get("company")
        if company is None:
            raise serializers.ValidationError("Validación de miembro rechazada: no se pudo determinar la empresa.")
        members = Member.objects.filter(company=company, member_code=value)
        if self.instance:
            members = members.exclude(id=self.instance.id)
        if members.exists():
            raise serializers.ValidationError("Validación de miembro rechazada: el código de miembro ya existe en esta empresa.")
        return value