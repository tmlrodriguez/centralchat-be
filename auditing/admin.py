from django.contrib import admin
from .models import AuditEvent

# Register your auditing models here.

@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["id", "occurred_at", "company", "branch", "actor", "category", "action", "severity", "target_model", "target_id"]
    list_filter = ["category", "action", "severity", "company", "branch"]
    search_fields = ["description", "target_label", "target_model", "target_id", "request_id", "actor__email"]
    ordering = ["-occurred_at", "-id"]
    readonly_fields = ["id", "company", "branch", "actor", "category", "action", "severity", "target_app", "target_model", "target_id", "target_label", "description", "metadata", "request_id", "ip_address", "user_agent", "occurred_at", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            return

        super().save_model(request, obj, form, change)