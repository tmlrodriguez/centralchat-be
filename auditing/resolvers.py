from django.shortcuts import get_object_or_404
from organizations.models import Company
from .models import AuditEvent

# Define your tenant-safe auditing resolvers here.

def resolve_administrative_audit_company(user, company_id):
    """
        DOCSTRING: Resolve Administrative Audit Company

        Description:
        - Resolve an active company owned by the authenticated organization administrator.

        Notes:
        - Audit access follows the same administrative company ownership boundary used by existing administrative APIs.
        - Foreign company identifiers intentionally return not found.
    """

    return get_object_or_404(Company, id=company_id, created_by=user, is_active=True)


def resolve_company_audit_event(company, event_id):
    """
        DOCSTRING: Resolve Company Audit Event

        Description:
        - Resolve an audit event strictly inside the supplied company tenant.

        Notes:
        - Foreign audit event identifiers intentionally return not found.
        - System-wide events without a company are not exposed through company-scoped endpoints.
    """
    return get_object_or_404(AuditEvent.objects.select_related("company", "branch", "actor"), id=event_id, company=company)