from django.contrib.auth.models import UserManager as DjangoUserManager
from .registry import ROLE_REGISTRY

# Define your managers here.

class AccessUserManager(DjangoUserManager):
    """
    DOCSTRING: Access User Manager

    Description:
    - Provide Dialoqo-specific user creation behavior.

    Notes:
    - Django superusers are automatically assigned the SUPERADMINISTRATOR role.
    """

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        """
        DOCSTRING: Create Superuser

        Description:
        - Create a Django superuser with the Dialoqo SUPERADMINISTRATOR role.

        Notes:
        - The SUPER_ADMINISTRATOR role is assigned automatically.
        - The resulting user receives Django staff and superuser privileges.
        """
        extra_fields["role"] = ROLE_REGISTRY.SUPER_ADMINISTRATOR
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return super().create_superuser(username=username, email=email, password=password, **extra_fields)