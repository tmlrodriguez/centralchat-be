# Docstring Guidelines

## Purpose

This document defines the required docstring standard for the CentralChat project.

Docstrings must clearly communicate the responsibility, behavior, constraints, and architectural intent of the code element they document. They are part of the project's maintainability standard and must be written consistently across the backend.

CentralChat does not use source-code comments for implementation explanation. Code must rely on clear naming, small responsibilities, explicit architecture, and properly structured docstrings.

## Required Docstring Structure

Every required docstring must contain the literal label:

```text
DOCSTRING:
```

The required structure is:

```python
"""
DOCSTRING: Item Name

Description:
- Explain what the item represents or is responsible for.
- Describe its primary behavior or purpose.

Notes:
- Document important domain rules.
- Document relevant security or authorization constraints.
- Document transaction or concurrency requirements when applicable.
- Document important architectural boundaries or side effects.
"""
```

Every required docstring must contain:

1. `DOCSTRING:` followed by the item name.
2. `Description:`
3. At least one description bullet.
4. `Notes:`
5. At least one note bullet.

## Items That Require Docstrings

Docstrings are mandatory for the following:

- Standalone functions.
- Classes.
- Django models.
- Django views.
- Django `APIView` classes.
- Django ViewSets.
- Serializers.
- Services.
- Workflows.
- Operations.
- Selectors.
- Query services.
- Permission classes.
- WebSocket consumers.
- Celery tasks.
- Integration clients.
- Webhook parsers.
- Webhook handlers.
- Custom exception classes.
- Custom managers and querysets when explicitly created.

No required item should be added to the codebase without a valid docstring.

## Class Methods

Class methods do not require an individual docstring by default.

A class method should have its own docstring when it contains significant behavior such as:

- Domain lifecycle transitions.
- Security-sensitive authorization.
- Tenant isolation rules.
- Concurrency-sensitive operations.
- Assignment lifecycle behavior.
- Monitoring activation or deactivation rules.
- Message edit or revocation behavior.
- Non-obvious integration behavior.

Small methods whose responsibility is already clear from the class and method name do not require redundant documentation.

## Writing Style

Docstrings must:

- Be written in English.
- Be technically precise.
- Be concise but sufficiently descriptive.
- Explain responsibility rather than implementation line by line.
- Use explicit domain terminology.
- Describe important invariants and restrictions.
- Describe side effects when relevant.
- Describe transaction requirements when relevant.
- Describe authorization boundaries when relevant.
- Remain synchronized with the implementation.

Avoid vague statements such as:

```text
- Handles data.
- Processes things.
- Manages WhatsApp.
- Does validation.
```

Prefer:

```text
- Resolve the WhatsApp number associated with an exact Meta phone_number_id.
- Reject access when the authenticated monitoring user does not have active company access.
- Preserve previous number assignments when responsibility is reassigned.
```

## Model Docstrings

Model docstrings must explain the model's domain responsibility and important lifecycle or integrity rules.

Example:

```python
class WhatsAppNumber(models.Model):
    """
    DOCSTRING: WhatsApp Number

    Description:
    - Represent a corporate WhatsApp number registered in CentralChat.
    - Associate the number with its company, branch, and WhatsApp Business Account.

    Notes:
    - Monitoring must begin through an explicit activation operation.
    - monitoring_started_at defines the beginning of monitored message history.
    - Current member responsibility must be resolved through NumberAssignment.
    - Historical assignments must never be overwritten.
    """
```

Do not simply repeat every model field in the docstring.

## Operation Docstrings

Operations represent explicit business actions and must document the business transition they perform.

Example:

```python
class ReassignWhatsAppNumberOperation:
    """
    DOCSTRING: Reassign WhatsApp Number Operation

    Description:
    - End the current active number assignment and create a new assignment.
    - Preserve the complete assignment history for the WhatsApp number.

    Notes:
    - The operation must execute inside transaction.atomic().
    - The WhatsApp number and current assignment must be locked where required.
    - The new member must belong to the same company as the WhatsApp number.
    - Only one active assignment may exist for a number.
    """
```

## Service Docstrings

Services must describe the reusable capability they provide.

Example:

```python
class MediaStorageService:
    """
    DOCSTRING: Media Storage Service

    Description:
    - Store and retrieve monitored WhatsApp media through the configured private object storage provider.

    Notes:
    - Binary media must not be stored directly in PostgreSQL.
    - Stored attachments must remain private.
    - Public permanent URLs must not be generated.
    - Storage-provider implementation details must remain isolated from the core domain.
    """
```

## Selector Docstrings

Selectors must describe the data they return and the authorization or scoping rules they enforce.

Example:

```python
def get_accessible_whatsapp_numbers(user):
    """
    DOCSTRING: Get Accessible WhatsApp Numbers

    Description:
    - Return WhatsApp numbers available to the authenticated monitoring user.
    - Scope results through the companies the user is explicitly authorized to monitor.

    Notes:
    - The selector must be read-only.
    - Administrator role must not implicitly grant monitoring access.
    - Company identifiers supplied by the client must not bypass access scoping.
    """
```

Selectors must never perform mutations.

## View Docstrings

View docstrings must describe the HTTP responsibility and relevant authorization boundaries.

Example:

```python
class ConversationMessageListView(APIView):
    """
    DOCSTRING: Conversation Message List View

    Description:
    - Return stored messages for an authorized monitored conversation.
    - Provide paginated chronological access to captured conversation history.

    Notes:
    - Only monitoring users with company access may retrieve messages.
    - Administrators must be denied access to conversation content.
    - Conversation authorization must be enforced by the backend.
    """
```

Views should remain thin and should not document business logic that belongs to operations or services.

## Serializer Docstrings

Serializer docstrings must describe the input or representation responsibility and important exposure restrictions.

Example:

```python
class WhatsAppNumberSerializer(serializers.ModelSerializer):
    """
    DOCSTRING: WhatsApp Number Serializer

    Description:
    - Serialize WhatsApp number configuration data for authorized administrative operations.

    Notes:
    - Meta access tokens and integration secrets must never be exposed.
    - Conversation or message content must not be included in administrative serializers.
    """
```

## Permission Class Docstrings

Permission classes must explicitly state the security boundary they enforce.

Example:

```python
class IsMonitoringUser(BasePermission):
    """
    DOCSTRING: Is Monitoring User Permission

    Description:
    - Restrict access to authenticated users with the monitoring role.

    Notes:
    - Monitoring role alone does not grant access to every company.
    - Company-level access must be validated separately.
    - Administrator role must not satisfy this permission.
    """
```

## WebSocket Consumer Docstrings

WebSocket consumers must document connection authorization and realtime security boundaries.

Example:

```python
class ConversationConsumer(AsyncJsonWebsocketConsumer):
    """
    DOCSTRING: Conversation Consumer

    Description:
    - Deliver near-real-time conversation events to authorized monitoring users.

    Notes:
    - Authorization must be validated before joining a conversation group.
    - Administrators must not be allowed to subscribe to conversation channels.
    - WebSocket group names must never be treated as authorization controls.
    - Company isolation must be enforced before realtime publication.
    """
```

## Celery Task Docstrings

Celery task docstrings must explain the background responsibility, retry considerations, and important security restrictions.

Example:

```python
def download_message_media(attachment_id):
    """
    DOCSTRING: Download Message Media

    Description:
    - Retrieve WhatsApp media from Meta and persist it through the configured private object storage backend.

    Notes:
    - The task must not log access tokens or private message content.
    - Retries must be limited to recoverable integration or infrastructure failures.
    - Database state must remain consistent when media retrieval fails.
    """
```

## Integration Component Docstrings

Meta-specific components must clearly document the external boundary they represent.

Example:

```python
class MetaWebhookParser:
    """
    DOCSTRING: Meta Webhook Parser

    Description:
    - Parse supported Meta WhatsApp webhook payloads into normalized internal events.

    Notes:
    - Raw Meta dictionaries must not be passed into core domain operations.
    - Unsupported event types must fail gracefully.
    - Parsing must not determine tenant authorization independently of the resolved WhatsApp number.
    """
```

## Standalone Function Docstrings

Every standalone function requires a docstring.

Example:

```python
def resolve_whatsapp_number(phone_number_id):
    """
    DOCSTRING: Resolve WhatsApp Number

    Description:
    - Resolve the internal WhatsAppNumber associated with the supplied Meta phone_number_id.

    Notes:
    - Resolution must use an exact identifier match.
    - The function must never silently fall back to another number.
    - Unknown identifiers must produce a controlled error.
    """
```

## Custom Exception Docstrings

Custom exceptions must explain the domain or integration failure they represent.

Example:

```python
class UnknownWhatsAppNumberError(Exception):
    """
    DOCSTRING: Unknown WhatsApp Number Error

    Description:
    - Represent failure to resolve a registered WhatsApp number from a Meta phone number identifier.

    Notes:
    - The exception must not expose credentials or sensitive Meta integration details.
    """
```

## Source-Code Comments

CentralChat does not use source-code comments for implementation explanation.

Do not write:

```python
# Validate company access
# Resolve assignment
# Store message
# Publish to websocket
```

Do not use decorative separators such as:

```python
# =========================
# SERVICES
# =========================
```

Code should communicate intent through:

- Clear names.
- Small functions.
- Explicit domain objects.
- Focused modules.
- Services and operations with clear responsibilities.
- Structured docstrings.

## Information That Must Not Appear in Docstrings

Never include:

- Secrets.
- Meta access tokens.
- Webhook verification secrets.
- Database passwords.
- Object storage credentials.
- Customer conversation content.
- Private webhook payloads.
- Temporary debugging information.
- TODO discussions.
- Changelog history.
- Developer conversations.

## Docstring Review Checklist

Before approving code, verify:

- Every required function and class has a docstring.
- Every required docstring contains `DOCSTRING:`.
- The item name is clear.
- `Description:` is present.
- `Notes:` is present.
- The description reflects the actual responsibility.
- Important domain rules are documented.
- Important security boundaries are documented.
- Transaction or concurrency requirements are documented where relevant.
- No source-code comments are being used as a substitute for documentation.
- No sensitive information appears in the docstring.
- The docstring remains accurate after implementation changes.
