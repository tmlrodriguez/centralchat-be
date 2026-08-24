from django.db import models

# Define your auditing registries here.

class AUDIT_CATEGORY_REGISTRY(models.TextChoices):
    ACCESS = "ACCESS", "Access"
    ORGANIZATION = "ORGANIZATION", "Organization"
    MEMBER = "MEMBER", "Member"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    META = "META", "Meta"
    SECURITY = "SECURITY", "Security"
    SYSTEM = "SYSTEM", "System"


class AUDIT_ACTION_REGISTRY(models.TextChoices):
    CREATE = "CREATE", "Create"
    UPDATE = "UPDATE", "Update"
    DELETE = "DELETE", "Delete"
    ACTIVATE = "ACTIVATE", "Activate"
    DEACTIVATE = "DEACTIVATE", "Deactivate"
    ASSIGN = "ASSIGN", "Assign"
    UNASSIGN = "UNASSIGN", "Unassign"
    CONNECT = "CONNECT", "Connect"
    DISCONNECT = "DISCONNECT", "Disconnect"
    VALIDATE = "VALIDATE", "Validate"
    OPEN = "OPEN", "Open"
    READ = "READ", "Read"
    SEND = "SEND", "Send"
    SYNCHRONIZE = "SYNCHRONIZE", "Synchronize"
    LOGIN = "LOGIN", "Login"
    LOGOUT = "LOGOUT", "Logout"
    GRANT = "GRANT", "Grant"
    REVOKE = "REVOKE", "Revoke"


class AUDIT_SEVERITY_REGISTRY(models.TextChoices):
    INFO = "INFO", "Info"
    WARNING = "WARNING", "Warning"
    CRITICAL = "CRITICAL", "Critical"