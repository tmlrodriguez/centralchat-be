from django.urls import path
from .views import ConversationReadView, ConversationView, MediaAttachmentView, MessageView, NumberAssignmentView, WhatsAppBusinessAccountView, WhatsAppMonitoringView, WhatsAppNumberView

# Define your urls here.

app_name = "whatsapp"

urlpatterns = [
    path("companies/<int:company_id>/accounts/", WhatsAppBusinessAccountView.as_view(), name="account-list-create"),
    path("companies/<int:company_id>/accounts/<int:account_id>/", WhatsAppBusinessAccountView.as_view(), name="account-detail"),
    path("companies/<int:company_id>/branches/<int:branch_id>/numbers/", WhatsAppNumberView.as_view(), name="number-list-create"),
    path("companies/<int:company_id>/branches/<int:branch_id>/numbers/<int:number_id>/", WhatsAppNumberView.as_view(), name="number-detail"),
    path("companies/<int:company_id>/branches/<int:branch_id>/numbers/<int:number_id>/monitoring/", WhatsAppMonitoringView.as_view(), name="number-monitoring"),
    path("companies/<int:company_id>/branches/<int:branch_id>/numbers/<int:number_id>/assignments/", NumberAssignmentView.as_view(), name="assignment-list-create"),
    path("companies/<int:company_id>/branches/<int:branch_id>/numbers/<int:number_id>/assignments/<int:assignment_id>/", NumberAssignmentView.as_view(), name="assignment-detail"),
    path("companies/<int:company_id>/branches/<int:branch_id>/numbers/<int:number_id>/conversations/", ConversationView.as_view(), name="conversation-list"),
    path("companies/<int:company_id>/branches/<int:branch_id>/numbers/<int:number_id>/conversations/<int:conversation_id>/", ConversationView.as_view(), name="conversation-detail"),
    path("companies/<int:company_id>/branches/<int:branch_id>/numbers/<int:number_id>/conversations/<int:conversation_id>/read/", ConversationReadView.as_view(), name="conversation-read"),
    path("companies/<int:company_id>/branches/<int:branch_id>/numbers/<int:number_id>/conversations/<int:conversation_id>/messages/", MessageView.as_view(), name="message-list"),
    path("companies/<int:company_id>/branches/<int:branch_id>/numbers/<int:number_id>/conversations/<int:conversation_id>/messages/<int:message_id>/", MessageView.as_view(), name="message-detail"),
    path("companies/<int:company_id>/branches/<int:branch_id>/numbers/<int:number_id>/conversations/<int:conversation_id>/messages/<int:message_id>/attachments/", MediaAttachmentView.as_view(), name="attachment-list"),
    path("companies/<int:company_id>/branches/<int:branch_id>/numbers/<int:number_id>/conversations/<int:conversation_id>/messages/<int:message_id>/attachments/<int:attachment_id>/", MediaAttachmentView.as_view(), name="attachment-detail"),
]