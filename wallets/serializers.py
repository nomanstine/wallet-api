from decimal import Decimal

from rest_framework import serializers

from tenants.models import TenantUser

from .models import Transaction, Wallet


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ["id", "user", "balance", "created_at", "updated_at"]
        read_only_fields = ["id", "balance", "created_at", "updated_at"]


class WalletCreateSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField()

    class Meta:
        model = Wallet
        fields = ["user_id", "currency"]

    def validate_user_id(self, value):
        tenant = self.context["request"].tenant
        if not TenantUser.objects.filter(tenant=tenant, id=value).exists():
            raise serializers.ValidationError("No such user for this tenant.")
        return value

    def create(self, validated_data):
        request = self.context["request"]
        user_id = validated_data.pop("user_id")
        return Wallet.objects.create(
            tenant=request.tenant,
            user_id=user_id,
            currency=validated_data.get("currency", "USD"),
        )


class AmountActionSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    idempotency_key = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class TransferSerializer(serializers.Serializer):
    from_wallet_id = serializers.UUIDField()
    to_wallet_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    idempotency_key = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class TransactionSerializer(serializers.ModelSerializer):
    wallet_id = serializers.UUIDField(source="wallet.id", read_only=True)
    transfer_id = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id", "wallet_id", "type", "amount", "balance_after",
            "transfer_id", "description", "created_at",
        ]

    def get_transfer_id(self, obj):
        return str(obj.transfer_id) if obj.transfer_id else None
