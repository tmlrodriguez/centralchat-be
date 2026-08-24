import uuid

from .context import clear_audit_request_context, set_audit_request_context


# Define your auditing middleware here.

class AuditRequestContextMiddleware:
    """
        DOCSTRING: Audit Request Context Middleware

        Description:
        - Capture request metadata required by the auditing subsystem.
        - Provide request identifiers, client IP addresses, and user-agent information to business operations.

        Notes:
        - Authentication credentials, cookies, and authorization headers are never stored.
        - REMOTE_ADDR is used as the client address until trusted-proxy handling is explicitly configured.
        - Existing X-Request-ID values are reused when supplied.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        ip_address = request.META.get("REMOTE_ADDR") or ""
        user_agent = request.headers.get("User-Agent") or ""

        request.audit_request_id = request_id

        token = set_audit_request_context(request_id=request_id, ip_address=ip_address, user_agent=user_agent)

        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response

        finally:
            clear_audit_request_context(token)