from rest_framework import generics, status
from rest_framework.response import Response

from .models import Tenant, TenantUser
from .permissions import HasTenant
from .serializers import TenantCreateResponseSerializer, TenantSerializer, TenantUserSerializer

class TenantListCreateView(generics.ListCreateAPIView):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = []
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        response_serializer = TenantCreateResponseSerializer(tenant)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class TenantUserListCreateView(generics.ListCreateAPIView):
    serializer_class = TenantUserSerializer
    permission_classes = [HasTenant]

    def get_queryset(self):
        return TenantUser.objects.filter(tenant=self.request.tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)
