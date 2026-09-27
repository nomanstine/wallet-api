from django.urls import path

from .views import TenantCreateView, TenantUserListCreateView

urlpatterns = [
    path("tenants/", TenantCreateView.as_view(), name="tenant-create"),
    path("users/", TenantUserListCreateView.as_view(), name="user-list-create"),
]
