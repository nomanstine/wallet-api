from rest_framework.test import APIClient

from tenants.models import Tenant, TenantUser

from ..models import Wallet


def create_tenant(name="Acme"):
    return Tenant.objects.create(name=name)


def create_user(tenant, name="Alice", email=None):
    email = email or f"{name.lower()}@example.com"
    return TenantUser.objects.create(tenant=tenant, name=name, email=email)


def create_wallet(tenant, user, currency="USD", balance="0.00"):
    return Wallet.objects.create(tenant=tenant, user=user, currency=currency, balance=balance)


def client_for(tenant):
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=tenant.api_key)
    return client
