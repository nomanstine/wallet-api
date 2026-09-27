from django.contrib import admin

from .models import IdempotencyKey, Transaction, Transfer, Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "user", "currency", "balance", "created_at")
    list_filter = ("tenant", "currency")
    readonly_fields = ("id", "created_at")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "wallet", "type", "amount", "balance_after", "created_at")
    list_filter = ("tenant", "type")
    readonly_fields = [f.name for f in Transaction._meta.fields]

    def has_change_permission(self, request, obj=None):
        return False  # ledger is immutable


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "from_wallet", "to_wallet", "amount", "created_at")


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("key", "tenant", "action", "response_status", "created_at")
    list_filter = ("tenant", "action")
