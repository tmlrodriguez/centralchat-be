from django.db import models

# Define your registries here.

class ROLE_REGISTRY(models.TextChoices):
    """
        DOCSTRING: Role Registry

        Description:
        - Define the application roles available to Dialoqo users.

        Notes:
        - SUPERADMINISTRATOR users may create ADMINISTRATOR users.
        - ADMINISTRATOR users may create MONITOR and MEMBER users.
        - MONITOR users cannot create application users.
        - MEMBER users cannot create application users.
    """

    SUPER_ADMINISTRATOR = "SUPER_ADMINISTRATOR", "Super Administrator"
    ADMINISTRATOR = "ADMINISTRATOR", "Administrator"
    MONITOR = "MONITOR", "Monitor"
    MEMBER = "MEMBER", "Member"