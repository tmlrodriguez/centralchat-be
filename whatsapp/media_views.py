from django.http import FileResponse
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST
from rest_framework.views import APIView
from .permissions import IsMonitoringUser
from .media import MetaMediaError, store_media_attachment
from .resolvers import resolve_conversation_message, resolve_message_media_attachment, resolve_monitoring_whatsapp_number, resolve_whatsapp_number_conversation
from .storage import private_whatsapp_media_storage

# Define your media views here.

class MediaAttachmentContentView(APIView):
    """
        DOCSTRING: Media Attachment Content View

        Description:
        - Return the private binary content associated with a monitored WhatsApp media attachment.
        - Retrieve and cache media from Meta when the binary has not yet been stored locally.

        Notes:
        - MONITOR and MEMBER users may retrieve media only when authorized for the source number.
        - Role-specific number authorization is resolved before conversation content is exposed.
        - Conversation is resolved inside the WhatsApp number.
        - Message is resolved inside the conversation.
        - Attachment is resolved inside the message.
        - Foreign resource identifiers therefore behave as nonexistent.
        - Internal private-storage keys are never returned through the API.
        - Binary files are streamed only through this authenticated endpoint.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsMonitoringUser]

    def get(self, request, company_id, branch_id, number_id, conversation_id, message_id, attachment_id):
        whatsapp_number = resolve_monitoring_whatsapp_number(user=request.user, company_id=company_id, branch_id=branch_id, number_id=number_id)
        conversation = resolve_whatsapp_number_conversation(whatsapp_number=whatsapp_number, conversation_id=conversation_id)
        message = resolve_conversation_message(conversation=conversation, message_id=message_id)
        attachment = resolve_message_media_attachment(message=message, attachment_id=attachment_id)

        attachment_available = attachment.is_stored and attachment.storage_key and private_whatsapp_media_storage.exists(attachment.storage_key)

        if not attachment_available:
            try:
                attachment = store_media_attachment(attachment)

            except MetaMediaError as error:
                response_payload = {
                    "error_message": "Obtención de adjunto rechazada: no fue posible recuperar el archivo multimedia.",
                    "data": {
                        "attachment": str(error),
                    },
                }

                return Response(response_payload, status=HTTP_400_BAD_REQUEST)

        file_handle = private_whatsapp_media_storage.open(attachment.storage_key, mode="rb")
        filename = attachment.original_filename or f"whatsapp-media-{attachment.id}"

        return FileResponse(file_handle, as_attachment=False, filename=filename, content_type=attachment.mime_type)