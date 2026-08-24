from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

# Define your template pagination classes here.

class MessageTemplatePagination(PageNumberPagination):
    """
        DOCSTRING: Message Template Pagination

        Description:
        - Provide page-number pagination for WhatsApp message-template catalogs.

        Notes:
        - Clients may customize page size within the configured maximum.
        - Pagination protects the template catalog endpoint from excessively large responses.
    """

    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            {
                "success_message": (
                    "Plantillas de WhatsApp extraídas correctamente."
                ),
                "data": {
                    "count": self.page.paginator.count,
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                    "results": data,
                },
            }
        )