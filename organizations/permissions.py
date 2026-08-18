from rest_framework.permissions import BasePermission
from access.registry import ROLE_REGISTRY

# Define your permissions here.

class IsOrganizationAdministrator(BasePermission):
    """
        DOCSTRING: Is Organization Administrator Permission

        Description:
        - Restrict organizational configuration endpoints to authenticated SUPERADMINISTRATOR and ADMINISTRATOR users.

        Notes:
        - MONITOR users must not create, update, deactivate, or manage organizational configuration.
        - This permission must not be used to authorize monitored conversation content.
    """
    message = "Acceso rechazado: se requieren permisos administrativos."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role in [ROLE_REGISTRY.SUPER_ADMINISTRATOR, ROLE_REGISTRY.ADMINISTRATOR]