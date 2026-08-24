from datetime import datetime, time
from django.db.models import Q
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView
from organizations.permissions import IsOrganizationAdministrator
from .models import AuditEvent
from .pagination import AuditEventPagination
from .registry import AUDIT_ACTION_REGISTRY, AUDIT_CATEGORY_REGISTRY, AUDIT_SEVERITY_REGISTRY
from .resolvers import resolve_administrative_audit_company, resolve_company_audit_event
from .serializers.business import AuditEventSerializer
from .serializers.snapshots import AuditEventSnapshotSerializer

# Define your auditing views here.

class AuditEventView(APIView):
    """
        DOCSTRING: Audit Event View

        Description:
        - Return immutable audit history belonging to an administratively managed company.
        - Return detailed information for one company-scoped audit event.
        - Support administrative filtering and searching across audit history.

        Notes:
        - Only organization administrators may access this endpoint.
        - Audit events are read-only.
        - Company boundaries are resolved before audit-event identifiers.
        - Foreign audit event identifiers therefore behave as nonexistent.
        - Filtering is restricted to explicitly supported audit fields.
        - Invalid filter values return controlled validation responses.
        - Audit records cannot be created, updated, or deleted through this view.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsOrganizationAdministrator]
    business_serializer = AuditEventSerializer
    snapshot_serializer = AuditEventSnapshotSerializer
    pagination_class = AuditEventPagination

    def get(self, request, company_id, event_id=None):
        company = resolve_administrative_audit_company(user=request.user, company_id=company_id)

        if event_id:
            event = resolve_company_audit_event(company=company, event_id=event_id)

            response_payload = {
                "success_message": "Evento de auditoría extraído correctamente.",
                "data": self.business_serializer(event).data,
            }

            return Response(response_payload, status=HTTP_200_OK)

        events = AuditEvent.objects.select_related("company", "branch", "actor").filter(company=company)

        category = request.query_params.get("category")
        action = request.query_params.get("action")
        severity = request.query_params.get("severity")
        actor_id = request.query_params.get("actor_id")
        branch_id = request.query_params.get("branch_id")
        target_app = request.query_params.get("target_app")
        target_model = request.query_params.get("target_model")
        target_id = request.query_params.get("target_id")
        request_id = request.query_params.get("request_id")
        search = request.query_params.get("search", "").strip()
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if category:
            normalized_category = category.upper()

            if normalized_category not in AUDIT_CATEGORY_REGISTRY.values:
                response_payload = {
                    "error_message": "Filtro de auditoría rechazado: category contiene un valor inválido.",
                    "data": {
                        "category": f"Valores permitidos: {', '.join(AUDIT_CATEGORY_REGISTRY.values)}.",
                    },
                }

                return Response(response_payload, status=HTTP_400_BAD_REQUEST)

            events = events.filter(category=normalized_category)

        if action:
            normalized_action = action.upper()

            if normalized_action not in AUDIT_ACTION_REGISTRY.values:
                response_payload = {
                    "error_message": "Filtro de auditoría rechazado: action contiene un valor inválido.",
                    "data": {
                        "action": f"Valores permitidos: {', '.join(AUDIT_ACTION_REGISTRY.values)}.",
                    },
                }

                return Response(response_payload, status=HTTP_400_BAD_REQUEST)

            events = events.filter(action=normalized_action)

        if severity:
            normalized_severity = severity.upper()

            if normalized_severity not in AUDIT_SEVERITY_REGISTRY.values:
                response_payload = {
                    "error_message": "Filtro de auditoría rechazado: severity contiene un valor inválido.",
                    "data": {
                        "severity": f"Valores permitidos: {', '.join(AUDIT_SEVERITY_REGISTRY.values)}.",
                    },
                }

                return Response(response_payload, status=HTTP_400_BAD_REQUEST)

            events = events.filter(severity=normalized_severity)

        if actor_id:
            try:
                actor_id = int(actor_id)

            except (TypeError, ValueError):
                response_payload = {
                    "error_message": "Filtro de auditoría rechazado: actor_id no contiene un identificador válido.",
                    "data": {
                        "actor_id": "Debe proporcionar un identificador numérico válido.",
                    },
                }

                return Response(response_payload, status=HTTP_400_BAD_REQUEST)

            events = events.filter(actor_id=actor_id)

        if branch_id:
            try:
                branch_id = int(branch_id)

            except (TypeError, ValueError):
                response_payload = {
                    "error_message": "Filtro de auditoría rechazado: branch_id no contiene un identificador válido.",
                    "data": {
                        "branch_id": "Debe proporcionar un identificador numérico válido.",
                    },
                }

                return Response(response_payload, status=HTTP_400_BAD_REQUEST)

            events = events.filter(branch_id=branch_id, branch__company=company)

        if target_app:
            events = events.filter(target_app=target_app)

        if target_model:
            events = events.filter(target_model=target_model)

        if target_id:
            events = events.filter(target_id=str(target_id))

        if request_id:
            events = events.filter(request_id=request_id)

        if search:
            events = events.filter(
                Q(description__icontains=search)
                | Q(target_label__icontains=search)
                | Q(target_model__icontains=search)
                | Q(target_id__icontains=search)
                | Q(actor__username__icontains=search)
                | Q(actor__email__icontains=search)
                | Q(actor__first_name__icontains=search)
                | Q(actor__last_name__icontains=search)
            )

        if date_from:
            try:
                parsed_date_from = datetime.strptime(date_from, "%Y-%m-%d").date()

            except ValueError:
                response_payload = {
                    "error_message": "Filtro de auditoría rechazado: date_from contiene una fecha inválida.",
                    "data": {
                        "date_from": "Formato requerido: YYYY-MM-DD.",
                    },
                }

                return Response(response_payload, status=HTTP_400_BAD_REQUEST)

            start_datetime = timezone.make_aware(datetime.combine(parsed_date_from, time.min))
            events = events.filter(occurred_at__gte=start_datetime)

        if date_to:
            try:
                parsed_date_to = datetime.strptime(date_to, "%Y-%m-%d").date()

            except ValueError:
                response_payload = {
                    "error_message": "Filtro de auditoría rechazado: date_to contiene una fecha inválida.",
                    "data": {
                        "date_to": "Formato requerido: YYYY-MM-DD.",
                    },
                }

                return Response(response_payload, status=HTTP_400_BAD_REQUEST)

            end_datetime = timezone.make_aware(datetime.combine(parsed_date_to, time.max))
            events = events.filter(occurred_at__lte=end_datetime)

        if date_from and date_to and parsed_date_from > parsed_date_to:
            response_payload = {
                "error_message": "Filtro de auditoría rechazado: el rango de fechas no es válido.",
                "data": {
                    "date_from": "date_from no puede ser posterior a date_to.",
                    "date_to": "date_to no puede ser anterior a date_from.",
                },
            }

            return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        events = events.order_by("-occurred_at", "-id")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(events, request, view=self)
        response_data = self.snapshot_serializer(page, many=True).data
        
        return paginator.get_paginated_response(response_data)