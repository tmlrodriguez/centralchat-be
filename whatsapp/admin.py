from django.contrib import admin
from .models import WhatsAppBusinessAccount, WhatsAppNumber, NumberAssignment

# Register your models here.

admin.site.register(WhatsAppBusinessAccount)
admin.site.register(WhatsAppNumber)
admin.site.register(NumberAssignment)
