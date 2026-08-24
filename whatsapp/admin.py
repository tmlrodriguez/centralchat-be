from django.contrib import admin
from .models import Conversation, ConversationReadState, Customer, MediaAttachment, Message, MetaIntegration, NumberAssignment, WhatsAppBusinessAccount, WhatsAppMessageTemplate, WhatsAppNumber

# Register your models here.

admin.site.register(MetaIntegration)
admin.site.register(WhatsAppBusinessAccount)
admin.site.register(WhatsAppNumber)
admin.site.register(NumberAssignment)
admin.site.register(Customer)
admin.site.register(Conversation)
admin.site.register(Message)
admin.site.register(MediaAttachment)
admin.site.register(ConversationReadState)
admin.site.register(WhatsAppMessageTemplate)