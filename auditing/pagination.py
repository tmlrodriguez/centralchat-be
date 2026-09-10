from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

# Define your auditing pagination classes here.

class AuditEventPagination(PageNumberPagination):
    """
        DOCSTRING: Audit Event Pagination

        Description:
        - Provide page-number pagination for Dialoqo audit-event history.
        - Return pagination metadata required by administrative audit interfaces.

        Notes:
        - The default page size supports efficient audit-history browsing.
        - Clients may adjust page_size within the configured maximum.
        - Audit-event pagination remains read-only.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response({
            "success_message": "Eventos de auditoría extraídos correctamente.",
            "data": {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            },
        })