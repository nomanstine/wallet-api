import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from tenants.models import Tenant, TenantUser

class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='wallets')
    user = models.ForeignKey(TenantUser, on_delete=models.CASCADE, related_name='wallets')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    currency = models.CharField(max_length=5, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet({self.id}) tenant={self.tenant_id} balance={self.balance} {self.currency}"

class Transfer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='transfers')
    from_wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='outgoing_transfers')
    to_wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='incoming_transfers')
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Transaction(models.Model):

    class Type(models.TextChoices):
        DEPOSIT = "DEPOSIT", "Deposit"
        WITHDRAWAL = "WITHDRAWAL", "Withdrawal"
        TRANSFER_IN = "TRANSFER_IN", "Transfer In"
        TRANSFER_OUT = "TRANSFER_OUT", "Transfer Out"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='transactions')
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=20, choices=Type.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)
    transfer = models.ForeignKey(Transfer, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.type} {self.amount} on wallet={self.wallet_id}"


class IdempotencyKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='idempotency_keys')
    key = models.CharField(max_length=255)
    action = models.CharField(max_length=20)
    request_fingerprint = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "key"], name="unique_idempotency_key_per_tenant"),
        ]

    def __str__(self):
        return f"{self.tenant_id}:{self.key}"