from django.contrib.auth.models import AbstractUser
from django.db import models
from .registry import ROLE_REGISTRY
from .managers import AccessUserManager

# Define your models here.

class AccessUser(AbstractUser):
    """
    DOCSTRING: AccessUser

    Description:
    - Represent an authenticated CentralChat user.
    - Store the application role assigned to the user.

    Notes:
    - SUPERADMINISTRATOR users may create ADMINISTRATOR users.
    - ADMINISTRATOR users may create MONITOR users.
    - MONITOR users receive company access separately.
    - Administrative roles do not automatically grant access to monitored conversation content.
    """

    role = models.CharField(max_length=25, blank=False, null=False, choices=ROLE_REGISTRY.choices)

    objects = AccessUserManager()

    class Meta:
        db_table = "access_user"

    def __str__(self):
        return self.username