from rest_framework.permissions import BasePermission
from .registry import ROLE_REGISTRY

# Define your permissions here.

class IsSuperAdministrator(BasePermission):
    """
    DOCSTRING: Is Super Administrator Permission

    Description:
    - Restrict access to authenticated and active SUPERADMINISTRATOR users.

    Notes:
    - This permission is intended for platform-level administrative functionality.
    - It must not be used to authorize monitored conversation content.
    """

    message = "Access rejected: super administrator permission is required."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role == ROLE_REGISTRY.SUPER_ADMINISTRATOR


class IsAdministrator(BasePermission):
    """
    DOCSTRING: Is Administrator Permission

    Description:
    - Restrict access to authenticated and active ADMINISTRATOR users.

    Notes:
    - This permission is intended for administrative functionality.
    - It must not be used to authorize monitored conversation content.
    """

    message = "Access rejected: administrator permission is required."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role == ROLE_REGISTRY.ADMINISTRATOR


class IsMonitor(BasePermission):
    """
    DOCSTRING: Is Monitor Permission

    Description:
    - Restrict access to authenticated and active MONITOR users.

    Notes:
    - Monitor role alone does not grant access to every company.
    - Company-level authorization must be enforced separately.
    """

    message = "Access rejected: monitor permission is required."

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active and request.user.role == ROLE_REGISTRY.MONITOR