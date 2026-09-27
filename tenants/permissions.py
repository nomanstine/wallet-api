from rest_framework.permissions import BasePermission

class HasTenant(BasePermission):
    message = "Tenant could not be resolved. Provide X-Api-Key or X-Tenant-ID header."

    def has_permission(self, request, view):
        return getattr(request, 'tenant', None) is not None