from django.contrib import admin
from .models import Company, Branch, UserCompanyAccess

# Register your models here.

admin.site.register(Company)
admin.site.register(Branch)
admin.site.register(UserCompanyAccess)
