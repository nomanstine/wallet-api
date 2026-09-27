from django.contrib import admin

from .models import Tenant, TenantUser


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at", "updated_at")
    readonly_fields = ("id", "api_key", "created_at", "updated_at")


@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "tenant", "created_at", "updated_at")
    list_filter = ("tenant",)
    readonly_fields = ("id", "created_at", "updated_at")
