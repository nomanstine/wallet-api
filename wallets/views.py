from rest_framework import generics, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from tenants.permissions import HasTenant

from . import services
from .idempotency import run_idempotent
from .models import Transaction, Wallet
from .serializers import (
    AmountActionSerializer,
    TransactionSerializer,
    TransferSerializer,
    WalletCreateSerializer,
    WalletSerializer,
)


class WalletListCreateView(generics.ListCreateAPIView):
    permission_classes = [HasTenant]

    def get_queryset(self):
        return Wallet.objects.filter(tenant=self.request.tenant)

    def get_serializer_class(self):
        return WalletCreateSerializer if self.request.method == "POST" else WalletSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wallet = serializer.save()
        return Response(WalletSerializer(wallet).data, status=status.HTTP_201_CREATED)


class WalletDetailView(generics.RetrieveAPIView):
    serializer_class = WalletSerializer
    permission_classes = [HasTenant]
    lookup_url_kwarg = "wallet_id"

    def get_queryset(self):
        return Wallet.objects.filter(tenant=self.request.tenant)


class WalletTransactionsView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [HasTenant]

    def get_queryset(self):
        wallet = get_object_or_404(
            Wallet.objects.filter(tenant=self.request.tenant), id=self.kwargs["wallet_id"]
        )
        return Transaction.objects.filter(tenant=self.request.tenant, wallet=wallet)


class DepositView(APIView):
    permission_classes = [HasTenant]

    def post(self, request, wallet_id):
        serializer = AmountActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        def do_deposit():
            wallet, txn = services.deposit(request.tenant, wallet_id, data["amount"], data["description"])
            return status.HTTP_201_CREATED, {
                "wallet_id": str(wallet.id),
                "balance": str(wallet.balance),
                "transaction": TransactionSerializer(txn).data,
            }

        status_code, body, replayed = run_idempotent(
            tenant=request.tenant,
            key=data["idempotency_key"],
            action="deposit",
            fingerprint_data={"action": "deposit", "wallet_id": str(wallet_id), "amount": str(data["amount"])},
            fn=do_deposit,
        )
        response = Response(body, status=status_code)
        response["Idempotent-Replayed"] = "true" if replayed else "false"
        return response


class WithdrawView(APIView):
    permission_classes = [HasTenant]

    def post(self, request, wallet_id):
        serializer = AmountActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        def do_withdraw():
            wallet, txn = services.withdraw(request.tenant, wallet_id, data["amount"], data["description"])
            return status.HTTP_201_CREATED, {
                "wallet_id": str(wallet.id),
                "balance": str(wallet.balance),
                "transaction": TransactionSerializer(txn).data,
            }

        status_code, body, replayed = run_idempotent(
            tenant=request.tenant,
            key=data["idempotency_key"],
            action="withdraw",
            fingerprint_data={"action": "withdraw", "wallet_id": str(wallet_id), "amount": str(data["amount"])},
            fn=do_withdraw,
        )
        response = Response(body, status=status_code)
        response["Idempotent-Replayed"] = "true" if replayed else "false"
        return response


class TransferView(APIView):
    permission_classes = [HasTenant]

    def post(self, request):
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        def do_transfer():
            transfer_obj, out_txn, in_txn = services.transfer(
                request.tenant, data["from_wallet_id"], data["to_wallet_id"],
                data["amount"], data["description"],
            )
            return status.HTTP_201_CREATED, {
                "transfer_id": str(transfer_obj.id),
                "from_wallet_id": str(transfer_obj.from_wallet_id),
                "to_wallet_id": str(transfer_obj.to_wallet_id),
                "amount": str(transfer_obj.amount),
                "out_transaction": TransactionSerializer(out_txn).data,
                "in_transaction": TransactionSerializer(in_txn).data,
            }

        status_code, body, replayed = run_idempotent(
            tenant=request.tenant,
            key=data["idempotency_key"],
            action="transfer",
            fingerprint_data={
                "action": "transfer",
                "from_wallet_id": str(data["from_wallet_id"]),
                "to_wallet_id": str(data["to_wallet_id"]),
                "amount": str(data["amount"]),
            },
            fn=do_transfer,
        )
        response = Response(body, status=status_code)
        response["Idempotent-Replayed"] = "true" if replayed else "false"
        return response
