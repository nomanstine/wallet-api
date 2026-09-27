from django.urls import path

from .views import TenantListCreateView, TenantUserListCreateView

urlpatterns = [
    path("tenants/", TenantListCreateView.as_view(), name="tenant-list-create"),
    path("users/", TenantUserListCreateView.as_view(), name="user-list-create"),
]
