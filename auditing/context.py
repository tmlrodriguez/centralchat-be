from contextvars import ContextVar

# Define your auditing request context here.

_audit_request_context = ContextVar(
    "audit_request_context",
    default=None,
)


def set_audit_request_context(
    request_id="",
    ip_address="",
    user_agent="",
):
    """
        DOCSTRING: Set Audit Request Context

        Description:
        - Store request-specific metadata for the current execution context.

        Notes:
        - ContextVar is used instead of thread-local state so the implementation remains safe for ASGI execution.
        - Sensitive authentication values must never be stored in this context.
    """

    context = {
        "request_id": str(request_id or ""),
        "ip_address": str(ip_address or ""),
        "user_agent": str(user_agent or ""),
    }

    return _audit_request_context.set(context)


def get_audit_request_context():
    """
        DOCSTRING: Get Audit Request Context

        Description:
        - Return request metadata associated with the current execution context.

        Notes:
        - An empty dictionary is returned when the operation is not running inside an HTTP request.
        - Background tasks may therefore create audit events without request metadata.
    """

    return _audit_request_context.get() or {}


def clear_audit_request_context(token):
    """
        DOCSTRING: Clear Audit Request Context

        Description:
        - Restore the previous auditing request context.

        Notes:
        - Middleware must call this operation after every request.
        - Context restoration prevents metadata leakage between ASGI requests.
    """

    _audit_request_context.reset(token)