from django.http import JsonResponse
from rest_framework.exceptions import AuthenticationFailed

from .models import Tenant

class TenantMiddleware:

    # Paths that don't require a resolved tenant (onboarding, admin site).
    EXEMPT_PATH_PREFIXES = ("/api/tenants/", "/admin/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None

        if not request.path.startswith(self.EXEMPT_PATH_PREFIXES):
            try:
                tenant = self._resolve_tenant(request)
                request.tenant = tenant
            except AuthenticationFailed as e:
                return JsonResponse({"error": str(e)}, status=401)

        response = self.get_response(request)
        return response

    def _resolve_tenant(self, request):
        api_key = request.headers.get("X-API-Key")
        tenant_id = request.headers.get("X-Tenant-ID")

        if api_key:
            try:
                tenant = Tenant.objects.get(api_key=api_key)
                return tenant
            except Tenant.DoesNotExist:
                raise AuthenticationFailed("Invalid API key.")
        elif tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                return tenant
            except Tenant.DoesNotExist:
                raise AuthenticationFailed("Invalid tenant ID.")
        else:
            raise AuthenticationFailed("Missing tenant credentials: provide X-Api-Key or X-Tenant-ID header.")
