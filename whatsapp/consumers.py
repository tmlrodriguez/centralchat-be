from types import SimpleNamespace
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from access.permissions import IsMonitor
from organizations.models import UserCompanyAccess
from .models import WhatsAppNumber
from .realtime import get_whatsapp_number_group_name, get_whatsapp_user_group_name

# Define your WebSocket consumers here.

class WhatsAppMonitorConsumer(AsyncJsonWebsocketConsumer):
    """
        DOCSTRING: WhatsApp Monitor Consumer

        Description:
        - Provide the authenticated realtime WebSocket connection used by CentralChat monitors.
        - Subscribe an authorized monitor to one company-owned WhatsApp number.
        - Forward normalized backend events to the connected frontend.

        Notes:
        - Authentication is resolved before the consumer through TokenQueryAuthMiddleware.
        - The user must remain active and satisfy the existing IsMonitor permission.
        - The user must have active access to the company.
        - The WhatsApp number must belong to the requested active company.
        - Each connection joins a shared number group and a private user-specific group.
        - Clients do not modify business data through this WebSocket; business writes remain REST operations.
    """

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        company_id = self.scope["url_route"]["kwargs"]["company_id"]
        whatsapp_number_id = self.scope["url_route"]["kwargs"]["number_id"]
        authorized = await self.authorize_connection(
            user=user,
            company_id=company_id,
            whatsapp_number_id=whatsapp_number_id,
        )
        if not authorized:
            await self.close(code=4403)
            return
        self.company_id = company_id
        self.whatsapp_number_id = whatsapp_number_id
        self.number_group_name = get_whatsapp_number_group_name(
            company_id=company_id,
            whatsapp_number_id=whatsapp_number_id,
        )
        self.user_group_name = get_whatsapp_user_group_name(
            user_id=user.id,
            company_id=company_id,
            whatsapp_number_id=whatsapp_number_id,
        )
        await self.channel_layer.group_add(self.number_group_name, self.channel_name)
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()
        await self.send_json({"event": "connection.ready", "data": {"company_id": company_id, "whatsapp_number_id": whatsapp_number_id}})

    async def disconnect(self, close_code):
        if hasattr(self, "number_group_name"):
            await self.channel_layer.group_discard(self.number_group_name, self.channel_name)
        if hasattr(self, "user_group_name"):
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """
            DOCSTRING: Receive JSON

            Description:
            - Process limited client-to-server WebSocket control messages.

            Notes:
            - Business mutations are intentionally rejected through the WebSocket transport.
            - ping is supported so clients can verify connection liveness.
        """
        event_name = content.get("event") if isinstance(content, dict) else None
        if event_name == "ping":
            await self.send_json({"event": "pong", "data": {}})
            return
        await self.send_json({"event": "error", "data": {"message": "Operación WebSocket rechazada: el evento solicitado no es válido."}})

    async def realtime_event(self, event):
        """
            DOCSTRING: Realtime Event

            Description:
            - Forward a normalized backend realtime event to the connected monitor.

            Notes:
            - Event authorization is inherited from the group membership established during connection.
        """
        await self.send_json({"event": event["event"], "data": event.get("data", {})})

    @database_sync_to_async
    def authorize_connection(self, user, company_id, whatsapp_number_id):
        """
            DOCSTRING: Authorize Connection

            Description:
            - Validate monitor permission, active company access, and complete WhatsApp-number tenant ownership before joining realtime groups.

            Notes:
            - Cross-company WebSocket subscription attempts are rejected.
            - The number's branch, WABA, and Meta integration must all belong to the requested company.
            - Foreign resource identifiers do not reveal resource ownership.
        """
        permission_request = SimpleNamespace(user=user)

        if not IsMonitor().has_permission(permission_request, None):
            return False

        company_access_exists = UserCompanyAccess.objects.filter(
            user=user,
            company_id=company_id,
            is_active=True,
            company__is_active=True,
        ).exists()

        if not company_access_exists:
            return False

        number_exists = WhatsAppNumber.objects.filter(
            id=whatsapp_number_id,
            company_id=company_id,
            branch__company_id=company_id,
            branch__is_active=True,
            whatsapp_business_account__company_id=company_id,
            whatsapp_business_account__meta_integration__company_id=company_id,
            is_active=True,
        ).exists()

        return number_exists