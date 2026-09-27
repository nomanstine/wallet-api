from rest_framework import serializers
from .models import Tenant, TenantUser


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate_name(self, value):
        if Tenant.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError('A tenant with this name already exists.')
        return value


class TenantCreateResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'api_key', 'created_at']
        read_only_fields = fields


class TenantUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantUser
        fields = ['id', 'name', 'email', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_email(self, value):
        request = self.context.get('request')
        tenant = getattr(request, 'tenant', None)

        if tenant and TenantUser.objects.filter(tenant=tenant, email=value).exists():
            raise serializers.ValidationError('A user with this email already exists for this tenant.')

        return value
